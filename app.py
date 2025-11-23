from datetime import datetime, timedelta, timezone
import random

from flask import Flask, request, jsonify, g, render_template
import jwt
from functools import wraps

from cardjitsu.models import (
    db,
    seed_cards,
    Card,
    User,
    UserCard,
    Deck,
    DeckCard,
    Room,
    Move,
)

# ---------------- DEMO USER SEEDING (OUTSIDE create_app) ---------------- #


def _create_demo_user(username: str, password: str) -> None:
    """Create one demo user with 15 cards and an active 10-card deck."""
    if User.query.filter_by(username=username).first():
        return  # already exists

    # create user
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # give them 15 random cards
    all_cards = Card.query.all()
    if len(all_cards) < 15:
        raise RuntimeError("Card pool not seeded correctly")

    chosen_cards = random.sample(all_cards, 15)

    for c in chosen_cards:
        db.session.add(UserCard(user_id=user.id, card_id=c.id))
    db.session.commit()

    # make an active deck from the first 10 cards
    deck = Deck(user_id=user.id, name=f"{username}'s Deck", is_active=True)
    db.session.add(deck)
    db.session.flush()  # get deck.id

    for c in chosen_cards[:10]:
        db.session.add(DeckCard(deck_id=deck.id, card_id=c.id))

    db.session.commit()


def seed_demo_users() -> None:
    """Create base demo logins + decks if DB has no users."""
    if User.query.count() > 0:
        return  # already have real users, do nothing

    _create_demo_user("player1", "test123")
    _create_demo_user("player2", "test123")


# ---------------- APP FACTORY ---------------- #


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cardjitsu.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # WE NEED TO CHANGE THIS BEFORE REAL DEPLOY
    app.config["SECRET_KEY"] = "dev-secret-change-me"

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_cards()       # fill Card table once if empty
        seed_demo_users()  # create player1 / player2 demo accounts

    # ---------- helper functions for auth ---------- #

    def create_token(user_id: int) -> str:
        """Create a JWT that expires in 24 hours."""
        payload = {
            "sub": str(user_id),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        }
        return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

    def decode_token(token: str):
        """Decode JWT and return its payload."""
        return jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])

    def auth_required(fn):
        """Decorator to protect routes with JWT auth."""

        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")

            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401

            token = auth_header.split(" ", 1)[1]

            try:
                payload = decode_token(token)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

            try:
                user_id = int(payload["sub"])
            except (KeyError, ValueError, TypeError):
                return jsonify({"error": "Invalid token payload"}), 401

            user = User.query.get(user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404

            g.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    # ---------- helper functions for rooms ---------- #

    def generate_room_code(length: int = 6) -> str:
        """Generate a unique room code."""
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        while True:
            code = "".join(random.choice(chars) for _ in range(length))
            if not Room.query.filter_by(room_code=code).first():
                return code

    def compare_cards(card1: Card, card2: Card) -> int:
        """
        Return:
          0 -> draw
          1 -> card1 wins
          2 -> card2 wins
        Using fire/grass/water RPS + power tie-breaker.
        """
        if not card1 or not card2:
            return 0

        if card1.element == card2.element:
            if card1.power == card2.power:
                return 0
            return 1 if card1.power > card2.power else 2

        beats = {
            "fire": "grass",
            "grass": "water",
            "water": "fire",
        }

        if beats.get(card1.element) == card2.element:
            return 1
        if beats.get(card2.element) == card1.element:
            return 2
        return 0

    def resolve_move(move: Move, room: Room) -> None:
        """Resolve a move once both players have chosen a card."""
        c1 = Card.query.get(move.player1_card_id)
        c2 = Card.query.get(move.player2_card_id)

        result = compare_cards(c1, c2)

        winner_user_id = None
        if result == 1:
            winner_user_id = room.player1_id
            room.player1_score += 1
        elif result == 2:
            winner_user_id = room.player2_id
            room.player2_score += 1

        move.winner_user_id = winner_user_id
        move.resolved = True

        # ez win rule for now: first to 3 points
        if winner_user_id is not None and (
            room.player1_score >= 3 or room.player2_score >= 3
        ):
            room.status = "finished"
            room.winner_id = winner_user_id
            room.ended_at = datetime.utcnow()

        db.session.commit()

    # ---------------- ROUTES ---------------- #

    @app.route("/")
    def index():
        return render_template("login.html")

    # ---- Auth API ---- #

    @app.post("/api/register")
    def register():
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        if not username or not password:
            return jsonify({"error": "username and password required"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "username already taken"}), 400

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        all_cards = Card.query.all()
        if len(all_cards) < 15:
            return jsonify({"error": "Card pool not seeded correctly"}), 500

        chosen_cards = random.sample(all_cards, 15)
        for card in chosen_cards:
            db.session.add(UserCard(user_id=user.id, card_id=card.id))
        db.session.commit()

        token = create_token(user.id)

        return (
            jsonify(
                {
                    "message": "registered",
                    "token": token,
                    "user": {"id": user.id, "username": user.username},
                }
            ),
            201,
        )

    @app.post("/api/login")
    def login():
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        if not username or not password:
            return jsonify({"error": "username and password required"}), 400

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return jsonify({"error": "invalid credentials"}), 401

        token = create_token(user.id)

        return jsonify(
            {
                "message": "logged in",
                "token": token,
                "user": {"id": user.id, "username": user.username},
            }
        )

    # ---- User cards ---- #

    @app.get("/api/user/cards")
    @auth_required
    def get_user_cards():
        user = g.current_user

        rows = (
            db.session.query(UserCard, Card)
            .join(Card, UserCard.card_id == Card.id)
            .filter(UserCard.user_id == user.id)
            .all()
        )

        cards_payload = [
            {
                "user_card_id": uc.id,
                "card_id": c.id,
                "element": c.element,
                "power": c.power,
                "colour": c.colour,
                "name": c.name,
            }
            for uc, c in rows
        ]

        return jsonify({"cards": cards_payload})

    # ---- Deck endpoints ---- #

    @app.post("/api/decks")
    @auth_required
    def create_or_replace_deck():
        user = g.current_user
        data = request.get_json() or {}

        name = (data.get("name") or "Main Deck").strip()
        user_card_ids = data.get("user_card_ids") or []

        if not isinstance(user_card_ids, list) or len(user_card_ids) != 10:
            return (
                jsonify(
                    {
                        "error": "Deck must contain exactly 10 cards",
                        "got": len(user_card_ids),
                    }
                ),
                400,
            )

        rows = (
            UserCard.query.filter(
                UserCard.user_id == user.id,
                UserCard.id.in_(user_card_ids),
            ).all()
        )

        if len(rows) != 10:
            return jsonify({"error": "One or more cards do not belong to this user"}), 400

        Deck.query.filter_by(user_id=user.id, is_active=True).update(
            {"is_active": False}
        )

        deck = Deck(user_id=user.id, name=name, is_active=True)
        db.session.add(deck)
        db.session.flush()

        for uc in rows:
            db.session.add(DeckCard(deck_id=deck.id, card_id=uc.card_id))

        db.session.commit()

        return (
            jsonify(
                {
                    "message": "deck created",
                    "deck": {
                        "id": deck.id,
                        "name": deck.name,
                        "is_active": deck.is_active,
                    },
                }
            ),
            201,
        )

    @app.get("/api/decks/active")
    @auth_required
    def get_active_deck():
        user = g.current_user

        deck = (
            Deck.query.filter_by(user_id=user.id, is_active=True)
            .order_by(Deck.created_at.desc())
            .first()
        )

        if not deck:
            return jsonify({"deck": None}), 200

        rows = (
            db.session.query(DeckCard, Card)
            .join(Card, DeckCard.card_id == Card.id)
            .filter(DeckCard.deck_id == deck.id)
            .all()
        )

        cards_payload = [
            {
                "deck_card_id": dc.id,
                "card_id": c.id,
                "element": c.element,
                "power": c.power,
                "colour": c.colour,
                "name": c.name,
            }
            for dc, c in rows
        ]

        return jsonify(
            {
                "deck": {
                    "id": deck.id,
                    "name": deck.name,
                    "is_active": deck.is_active,
                    "cards": cards_payload,
                }
            }
        )

    # ---- Page routes (templates) ---- #

    @app.get("/home")
    def home_page():
        return render_template("home.html")

    @app.get("/rules")
    def rules_page():
        return render_template("rules.html")

    @app.get("/deckbuilding")
    def deckbuilding_page():
        return render_template("deckbuilding.html")

    @app.get("/register")
    def register_page():
        return render_template("register.html")

    @app.get("/login")
    def login_page():
        return render_template("login.html")

    @app.get("/mydeck")
    def mydeck_page():
        return render_template("mydeck.html")

    @app.get("/room")
    def room_page():
        return render_template("room.html")

    # ---- Room + match endpoints ---- #

    @app.post("/api/rooms")
    @auth_required
    def create_room():
        user = g.current_user

        active_deck = Deck.query.filter_by(user_id=user.id, is_active=True).first()
        if not active_deck:
            return jsonify({"error": "You must have an active deck to create a room"}), 400

        room_code = generate_room_code()

        room = Room(
            room_code=room_code,
            player1_id=user.id,
            status="waiting",
            player1_score=0,
            player2_score=0,
        )
        db.session.add(room)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "room created",
                    "room": {
                        "id": room.id,
                        "room_code": room.room_code,
                        "status": room.status,
                    },
                }
            ),
            201,
        )

    @app.post("/api/rooms/join")
    @auth_required
    def join_room():
        user = g.current_user
        data = request.get_json() or {}
        room_code = (data.get("room_code") or "").strip().upper()

        if not room_code:
            return jsonify({"error": "room_code required"}), 400

        room = Room.query.filter_by(room_code=room_code).first()
        if not room:
            return jsonify({"error": "Room not found"}), 404

        if room.status != "waiting":
            return jsonify({"error": "Room is not joinable"}), 400

        if room.player1_id == user.id:
            return jsonify({"error": "You are already player 1 in this room"}), 400

        active_deck = Deck.query.filter_by(user_id=user.id, is_active=True).first()
        if not active_deck:
            return jsonify({"error": "You must have an active deck to join a room"}), 400

        room.player2_id = user.id
        room.status = "active"
        room.started_at = datetime.utcnow()

        db.session.commit()

        return jsonify(
            {
                "message": "joined room",
                "room": {
                    "room_code": room.room_code,
                    "status": room.status,
                    "player1_id": room.player1_id,
                    "player2_id": room.player2_id,
                },
            }
        )

    @app.get("/api/rooms/<room_code>/state")
    @auth_required
    def room_state(room_code):
        user = g.current_user
        room = Room.query.filter_by(room_code=room_code.upper()).first()
        if not room:
            return jsonify({"error": "Room not found"}), 404

        if user.id not in (room.player1_id, room.player2_id):
            return jsonify({"error": "You are not part of this room"}), 403

        moves = (
            Move.query.filter_by(room_id=room.id)
            .order_by(Move.round_number.asc())
            .all()
        )

        moves_payload = [
            {
                "round_number": m.round_number,
                "resolved": m.resolved,
                "winner_user_id": m.winner_user_id,
            }
            for m in moves
        ]

        return jsonify(
            {
                "room": {
                    "room_code": room.room_code,
                    "status": room.status,
                    "player1_id": room.player1_id,
                    "player2_id": room.player2_id,
                    "player1_score": room.player1_score,
                    "player2_score": room.player2_score,
                    "winner_id": room.winner_id,
                },
                "moves": moves_payload,
            }
        )

    @app.post("/api/rooms/<room_code>/play")
    @auth_required
    def play_card(room_code):
        user = g.current_user
        data = request.get_json() or {}
        card_id = data.get("card_id")

        if not isinstance(card_id, int):
            return jsonify({"error": "card_id must be an integer"}), 400

        room = Room.query.filter_by(room_code=room_code.upper()).first()
        if not room:
            return jsonify({"error": "Room not found"}), 404

        if room.status != "active":
            return jsonify({"error": f"Room is not active (status={room.status})"}), 400

        if user.id not in (room.player1_id, room.player2_id):
            return jsonify({"error": "You are not part of this room"}), 403

        active_deck = Deck.query.filter_by(user_id=user.id, is_active=True).first()
        if not active_deck:
            return jsonify({"error": "You must have an active deck to play"}), 400

        in_deck = (
            db.session.query(DeckCard)
            .join(Deck, DeckCard.deck_id == Deck.id)
            .filter(
                Deck.id == active_deck.id,
                DeckCard.card_id == card_id,
            )
            .first()
        )

        if not in_deck:
            return jsonify({"error": "This card is not in your active deck"}), 400

        current_move = (
            Move.query.filter_by(room_id=room.id, resolved=False)
            .order_by(Move.round_number.desc())
            .first()
        )

        last_round = (
            Move.query.filter_by(room_id=room.id)
            .order_by(Move.round_number.desc())
            .first()
        )
        last_round_number = last_round.round_number if last_round else 0

        is_player1 = user.id == room.player1_id

        if not current_move:
            round_number = last_round_number + 1
            current_move = Move(
                room_id=room.id,
                round_number=round_number,
            )
            if is_player1:
                current_move.player1_card_id = card_id
            else:
                current_move.player2_card_id = card_id
            db.session.add(current_move)
            db.session.commit()
        else:
            if is_player1:
                if current_move.player1_card_id is not None:
                    return jsonify({"error": "You already played this round"}), 400
                current_move.player1_card_id = card_id
            else:
                if current_move.player2_card_id is not None:
                    return jsonify({"error": "You already played this round"}), 400
                current_move.player2_card_id = card_id
            db.session.commit()

        if (
            current_move.player1_card_id is not None
            and current_move.player2_card_id is not None
            and not current_move.resolved
        ):
            resolve_move(current_move, room)

        db.session.refresh(room)
        db.session.refresh(current_move)

        return jsonify(
            {
                "message": "move recorded",
                "room_status": room.status,
                "round": {
                    "round_number": current_move.round_number,
                    "resolved": current_move.resolved,
                    "winner_user_id": current_move.winner_user_id,
                },
                "scores": {
                    "player1_score": room.player1_score,
                    "player2_score": room.player2_score,
                    "winner_id": room.winner_id,
                },
            }
        )

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)