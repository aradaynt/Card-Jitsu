from datetime import datetime, timedelta
import random

from flask import Flask, request, jsonify, g
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
)


def create_app():
    app = Flask(__name__)

    # --- basic config ---
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cardjitsu.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # CHANGE THIS BEFORE DEPLOYING ANYWHERE REAL
    app.config["SECRET_KEY"] = "dev-secret-change-me"

    # --- init DB + seed cards ---
    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_cards()  # fills the Card table once if empty

    # ---------- helper functions ----------

    def create_token(user_id: int) -> str:
        """Create a JWT that expires in 24 hours."""
        payload = {
            "sub": user_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=24),
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

            user = User.query.get(payload["sub"])
            if not user:
                return jsonify({"error": "User not found"}), 404

            g.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    # ---------- routes ----------

    @app.route("/")
    def index():
        return "Card-Jitsu backend is running!"

    # POST /api/register  { "username": "...", "password": "..." }
    @app.post("/api/register")
    def register():
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        if not username or not password:
            return jsonify({"error": "username and password required"}), 400

        # ensure unique username
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "username already taken"}), 400

        # create user
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # give them 15 random cards from the global pool
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

    # POST /api/login  { "username": "...", "password": "..." }
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

    # GET /api/user/cards
    @app.get("/api/user/cards")
    @auth_required
    def get_user_cards():
        user = g.current_user

        # join UserCard -> Card so you can see full card info
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
        # ---------- DECK ENDPOINTS ----------

    # POST /api/decks
    # Body: { "name": "My Deck", "user_card_ids": [1,2,...,10] }
    @app.post("/api/decks")
    @auth_required
    def create_or_replace_deck():
        user = g.current_user
        data = request.get_json() or {}

        name = (data.get("name") or "Main Deck").strip()
        user_card_ids = data.get("user_card_ids") or []

        # must have exactly 10 cards
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

        # load the UserCard rows for this user and these ids
        rows = (
            UserCard.query.filter(
                UserCard.user_id == user.id,
                UserCard.id.in_(user_card_ids),
            ).all()
        )

        if len(rows) != 10:
            return jsonify({"error": "One or more cards do not belong to this user"}), 400

        # deactivate existing decks
        Deck.query.filter_by(user_id=user.id, is_active=True).update(
            {"is_active": False}
        )

        # create new deck
        deck = Deck(user_id=user.id, name=name, is_active=True)
        db.session.add(deck)
        db.session.flush()  # get deck.id before adding DeckCard rows

        # create DeckCard rows using the underlying Card ids
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

    # GET /api/decks/active
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

        # join DeckCard -> Card
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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)