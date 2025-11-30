"""
Flask application for the Card-Jitsu multiplayer game.

This module defines:
- Core game-logic helper functions (compare_cards, resolve_move, etc.).
- Demo user and card seeding utilities.
- The Flask application factory (create_app).
- All REST API endpoints for authentication, deck-building, rooms, and gameplay.
"""

from datetime import datetime, timedelta, timezone
import random
from functools import wraps
import itertools

from flask import Flask, request, jsonify, g, render_template, current_app
import jwt

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


# ---------------- GAME LOGIC HELPERS ---------------- #
def compare_cards(card1: Card, card2: Card) -> int:
    """
    Compare two cards using Card-Jitsu rules.

    First applies the element rock-paper-scissors logic:
    - fire beats grass
    - grass beats water
    - water beats fire

    If elements are the same, the higher power wins. If both element and
    power are the same, the result is a draw.

    Args:
        card1 (Card): First player's card.
        card2 (Card): Second player's card.

    Returns:
        int: 0 for draw, 1 if card1 wins, 2 if card2 wins.
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


def get_player_winning_cards(room: Room, player_index: int) -> list[Card]:
    """
    Return the list of cards a player has won in a room so far.

    This looks at all resolved moves in the room and collects the card
    used by the specified player in each round they won.

    Args:
        room (Room): The game room to inspect.
        player_index (int): 1 for player1, 2 for player2.

    Returns:
        list[Card]: Cards that the player has won, one per winning round.
    """
    if player_index not in (1, 2):
        return []

    player_id = room.player1_id if player_index == 1 else room.player2_id
    if not player_id:
        return []

    # All resolved moves where this player was the winner
    moves = (
        Move.query.filter_by(room_id=room.id, resolved=True, winner_user_id=player_id)
        .order_by(Move.round_number.asc())
        .all()
    )

    cards: list[Card] = []
    for m in moves:
        if player_index == 1:
            card_id = m.player1_card_id
        else:
            card_id = m.player2_card_id

        if card_id is None:
            continue

        c = Card.query.get(card_id)
        if c:
            cards.append(c)

    return cards


def has_club_penguin_win(cards: list[Card]) -> bool:
    """
    Check if a set of cards satisfies the Club Penguin win conditions.

    The player wins if ANY of these patterns is present among their
    winning cards:

    1) Three of the SAME element, with 3 DIFFERENT colours.
       Example: Fire-Red, Fire-Blue, Fire-Green
    2) Three of ALL DIFFERENT elements (fire, water, grass),
       with 3 DIFFERENT colours.
       Example: Fire-Red, Water-Blue, Grass-Green
    3) Three of ALL DIFFERENT elements but the SAME colour.
       Example: Fire-Red, Water-Red, Grass-Red

    Args:
        cards (list[Card]): All cards the player has won so far.

    Returns:
        bool: True if at least one winning pattern is found, False otherwise.
    """
    if len(cards) < 3:
        return False

    # Check all 3-card combinations for any of the win patterns
    for trio in itertools.combinations(cards, 3):
        elements = [c.element for c in trio]
        colours = [c.colour for c in trio]

        unique_elements = set(elements)
        unique_colours = set(colours)

        # Way 1: same element, all different colours
        if len(unique_elements) == 1 and len(unique_colours) == 3:
            return True

        # Way 2: all different elements, all different colours
        if len(unique_elements) == 3 and len(unique_colours) == 3:
            return True

        # Way 3: all different elements, same colour
        if len(unique_elements) == 3 and len(unique_colours) == 1:
            return True

    return False


def resolve_move(move: Move, room: Room) -> None:
    """
    Resolve a single move once both players have selected a card.

    This function:
    - Determines the round winner using compare_cards().
    - Updates the round's winner, room scores, and move state.
    - Checks if the Club Penguin win condition is now satisfied for
      either player and, if so, marks the room as finished and updates
      user statistics.

    Args:
        move (Move): The move (round) being resolved.
        room (Room): The room in which this move is played.
    """
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

    # ---- Club Penguin win condition ----
    final_winner_id = None

    # Check player 1's won cards
    if room.player1_id:
        p1_cards = get_player_winning_cards(room, player_index=1)
        if has_club_penguin_win(p1_cards):
            final_winner_id = room.player1_id

    # Check player 2's won cards (only if nobody has won yet)
    if final_winner_id is None and room.player2_id:
        p2_cards = get_player_winning_cards(room, player_index=2)
        if has_club_penguin_win(p2_cards):
            final_winner_id = room.player2_id

    if final_winner_id is not None:
        room.status = "finished"
        room.winner_id = final_winner_id
        room.ended_at = datetime.utcnow()

        # Figure out loser
        loser_id = None
        if final_winner_id == room.player1_id:
            loser_id = room.player2_id
        elif final_winner_id == room.player2_id:
            loser_id = room.player1_id

        # Update winner stats
        winner = User.query.get(final_winner_id)
        if winner:
            winner.win_count = (winner.win_count or 0) + 1
            winner.total_games = (winner.total_games or 0) + 1

        # Update loser stats
        if loser_id is not None:
            loser = User.query.get(loser_id)
            if loser:
                loser.total_games = (loser.total_games or 0) + 1

    db.session.commit()


# ---------------- DEMO USER SEEDING (OUTSIDE create_app) ---------------- #
def _create_demo_user(username: str, password: str) -> None:
    """
    Create a single demo user with a collection and active deck.

    The demo user is given:
    - A new User entry with the provided username and password.
    - 40 random UserCard entries (distinct cards).
    - One active Deck containing the first 25 of those 40 cards.

    If the username already exists, this function does nothing.

    Args:
        username (str): Username for the demo account.
        password (str): Plaintext password for the demo account.
    """
    if User.query.filter_by(username=username).first():
        return  # already exists

    # Create user
    user = User(username=username, win_count=0, total_games=0)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Give them 40 random cards
    all_cards = Card.query.all()
    if len(all_cards) < 40:
        raise RuntimeError("Card pool not seeded correctly (need at least 40 cards)")

    chosen_cards = random.sample(all_cards, 40)

    for c in chosen_cards:
        db.session.add(UserCard(user_id=user.id, card_id=c.id))
    db.session.commit()

    # Make an active deck from the first 25 cards
    deck = Deck(user_id=user.id, name=f"{username}'s Deck", is_active=True)
    db.session.add(deck)
    db.session.flush()  # get deck.id

    for c in chosen_cards[:25]:
        db.session.add(DeckCard(deck_id=deck.id, card_id=c.id))

    db.session.commit()


def seed_demo_users() -> None:
    """
    Create base demo users with decks if the database has no users.

    This is mainly for local development/testing so the game can be
    played right away using:
    - username: player1, password: test123
    - username: player2, password: test123
    """
    if User.query.count() > 0:
        return  # already have real users, do nothing

    _create_demo_user("player1", "test123")
    _create_demo_user("player2", "test123")


# ---------------- APP FACTORY ---------------- #
def create_app():
    """
    Create and configure the Flask application.

    This function:
    - Configures the Flask app and SQLAlchemy.
    - Creates tables and seeds the card pool and demo users.
    - Registers all helper functions and API routes.

    Returns:
        Flask: The configured Flask application instance.
    """
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cardjitsu.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # NOTE: Replace with a secure secret key before real deployment.
    app.config["SECRET_KEY"] = "dev-secret-change-me"

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_cards()       # Fill Card table once if empty
        seed_demo_users()  # Create player1 / player2 demo accounts

    # ---------- helper functions for auth ---------- #
    def create_token(user_id: int) -> str:
        """
        Create a JWT access token for a given user.

        The token uses the app's SECRET_KEY and is valid for 24 hours.

        Args:
            user_id (int): ID of the authenticated user.

        Returns:
            str: Encoded JWT token.
        """
        payload = {
            "sub": str(user_id),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        }
        return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

    def decode_token(token: str):
        """
        Decode a JWT access token.

        Args:
            token (str): Encoded JWT token.

        Returns:
            dict: Decoded token payload.

        Raises:
            jwt.ExpiredSignatureError: If the token has expired.
            jwt.InvalidTokenError: If the token is invalid for any reason.
        """
        return jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])

    def auth_required(fn):
        """
        Decorator to protect a route with JWT-based authentication.

        The decorator expects an Authorization header with a Bearer token.
        On success, the authenticated User is stored in `g.current_user`.

        Args:
            fn (Callable): View function to wrap.

        Returns:
            Callable: Wrapped view function enforcing authentication.
        """

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
        """
        Generate a unique alphanumeric room code.

        The code is composed of characters chosen to avoid ambiguity
        (e.g., no 0/O or 1/I).

        Args:
            length (int, optional): Desired code length. Defaults to 6.

        Returns:
            str: A unique room code not currently used in the database.
        """
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        while True:
            code = "".join(random.choice(chars) for _ in range(length))
            if not Room.query.filter_by(room_code=code).first():
                return code

    # ---------------- ROUTES ---------------- #
    @app.route("/")
    def index():
        """
        Render the login page (root route).
        """
        return render_template("login.html")

    # ---- Auth API ---- #
    @app.post("/api/register")
    def register():
        """
        Register a new user and create their initial card collection.

        Expects JSON payload with:
        - username (str)
        - password (str)

        The user is given 40 random cards and a JWT token is returned.

        Returns:
            Response: JSON with message, token, and user info.
        """
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        win_count = 0
        total_games = 0

        if not username or not password:
            return jsonify({"error": "username and password required"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "username already taken"}), 400

        user = User(username=username, win_count=win_count, total_games=total_games)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        all_cards = Card.query.all()
        if len(all_cards) < 40:
            return (
                jsonify(
                    {"error": "Card pool not seeded correctly (need at least 40 cards)"}
                ),
                500,
            )

        # Give the new user 40 distinct cards in their collection
        chosen_cards = random.sample(all_cards, 40)
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
        """
        Authenticate an existing user and return a JWT.

        Expects JSON payload with:
        - username (str)
        - password (str)

        Returns:
            Response: JSON with message, token, and basic user info.
        """
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
        """
        Return all cards owned by the current user.

        The result is a list of user-card entries joined with card data.

        Returns:
            Response: JSON object with a "cards" list.
        """
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
        """
        Create or replace the current user's active deck.

        Expects JSON with:
        - name (str, optional): Deck name. Defaults to "Main Deck".
        - user_card_ids (list[int]): Exactly 25 UserCard IDs belonging
          to the current user.

        Any existing active deck is deactivated before the new one is
        created.

        Returns:
            Response: JSON with a message and basic deck info.
        """
        user = g.current_user
        data = request.get_json() or {}

        name = (data.get("name") or "Main Deck").strip()
        user_card_ids = data.get("user_card_ids") or []

        if not isinstance(user_card_ids, list) or len(user_card_ids) != 25:
            return (
                jsonify(
                    {
                        "error": "Deck must contain exactly 25 cards",
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

        if len(rows) != 25:
            return jsonify({"error": "One or more cards do not belong to this user"}), 400

        # Deactivate any existing active deck for this user
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
        """
        Return the current user's active deck and its cards.

        Returns:
            Response: JSON with "deck" set to deck info and card list,
            or "deck": None if the user has no active deck.
        """
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

    @app.get("/api/decks")
    @auth_required
    def list_decks():
        """
        Return all decks for the current user.

        This is used by the UI to let players select which deck to
        activate.

        Returns:
            Response: JSON object with a "decks" list.
        """
        user = g.current_user

        decks = (
            Deck.query.filter_by(user_id=user.id)
            .order_by(Deck.id.desc())
            .all()
        )

        deck_payload = []
        for d in decks:
            card_count = (
                db.session.query(DeckCard)
                .filter_by(deck_id=d.id)
                .count()
            )

            deck_payload.append(
                {
                    "id": d.id,
                    "name": d.name,
                    "is_active": d.is_active,
                    "card_count": card_count,
                }
            )

        return jsonify({"decks": deck_payload})

    @app.post("/api/decks/<int:deck_id>/activate")
    @auth_required
    def activate_deck(deck_id: int):
        """
        Set one of the user's decks as the active deck.

        Args:
            deck_id (int): ID of the deck the user wants to activate.

        Returns:
            Response: JSON with message and basic deck info,
            or an error if the deck is not found.
        """
        user = g.current_user

        deck = Deck.query.filter_by(id=deck_id, user_id=user.id).first()
        if not deck:
            return jsonify({"error": "Deck not found"}), 404

        # Turn off old active deck(s)
        Deck.query.filter_by(user_id=user.id, is_active=True).update({"is_active": False})

        # Activate this one
        deck.is_active = True
        db.session.commit()

        return jsonify(
            {
                "message": "deck activated",
                "deck": {
                    "id": deck.id,
                    "name": deck.name,
                    "is_active": deck.is_active,
                },
            }
        )

    @app.get("/api/me")
    @auth_required
    def get_me():
        """
        Return the current user's basic profile and stats.

        Returns:
            Response: JSON with username, win_count, and total_games.
        """
        user = g.current_user

        return jsonify(
            {
                "username": user.username,
                "win_count": user.win_count,
                "total_games": user.total_games,
            }
        )

    # ---- Page routes (templates) ---- #
    @app.get("/home")
    def home_page():
        """Render the home page template."""
        return render_template("home.html")

    @app.get("/rules")
    def rules_page():
        """Render the rules page template."""
        return render_template("rules.html")

    @app.get("/deckbuilding")
    def deckbuilding_page():
        """Render the deck-building page template."""
        return render_template("deckbuilding.html")

    @app.get("/register")
    def register_page():
        """Render the registration page template."""
        return render_template("register.html")

    @app.get("/login")
    def login_page():
        """Render the login page template."""
        return render_template("login.html")

    @app.get("/mydeck")
    def mydeck_page():
        """Render the 'my deck' management page template."""
        return render_template("mydeck.html")

    @app.get("/room")
    def room_page():
        """Render the room page template."""
        return render_template("room.html")

    # ---- Room + match endpoints ---- #
    @app.post("/api/rooms")
    @auth_required
    def create_room():
        """
        Create a new room with the current user as player 1.

        Requires the user to have an active deck before creating a room.

        Returns:
            Response: JSON with message and room identifier info.
        """
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
        """
        Join an existing room as player 2.

        Expects JSON payload with:
        - room_code (str)

        The user must:
        - Not already be player 1 in that room.
        - Have an active deck.
        - The room must still be in "waiting" status.

        Returns:
            Response: JSON with message and room info, or error details.
        """
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
        """
        Return the current state of a room.

        This includes:
        - Room metadata (scores, players, status).
        - Last round's cards and winner.
        - All moves (for history).
        - All cards each player has won so far.

        Args:
            room_code (str): Public code used to identify the room.

        Returns:
            Response: JSON describing the room and its moves, or an error.
        """
        user = g.current_user
        room = Room.query.filter_by(room_code=room_code.upper()).first()
        if not room:
            return jsonify({"error": "Room not found"}), 404

        if user.id not in (room.player1_id, room.player2_id):
            return jsonify({"error": "You are not part of this room"}), 403

        # All moves for history / debugging
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

        # ---------- last cards played by each player ----------
        last_move = (
            Move.query.filter_by(room_id=room.id)
            .order_by(Move.round_number.desc())
            .first()
        )

        last_round_winner_username = None
        if last_move and last_move.winner_user_id:
            winner_user = User.query.get(last_move.winner_user_id)
            if winner_user:
                last_round_winner_username = winner_user.username

        # ---- helper for converting cards ----
        def card_to_payload(card: Card | None):
            """
            Convert a Card to a lightweight JSON payload.

            Args:
                card (Card | None): Card instance or None.

            Returns:
                dict | None: Dictionary with card fields, or None.
            """
            if not card:
                return None
            return {
                "id": card.id,
                "element": card.element,
                "power": card.power,
                "colour": card.colour,
                "name": card.name,
            }

        p1_last_card_payload = None
        p2_last_card_payload = None

        if last_move:
            if last_move.player1_card_id is not None:
                c1 = Card.query.get(last_move.player1_card_id)
                p1_last_card_payload = card_to_payload(c1)
            if last_move.player2_card_id is not None:
                c2 = Card.query.get(last_move.player2_card_id)
                p2_last_card_payload = card_to_payload(c2)

        # All cards P1 has won so far
        player1_won_cards = []
        if room.player1_id:
            for m in moves:
                if (
                    m.resolved
                    and m.winner_user_id == room.player1_id
                    and m.player1_card_id is not None
                ):
                    c = Card.query.get(m.player1_card_id)
                    if c:
                        player1_won_cards.append(card_to_payload(c))

        # All cards P2 has won so far
        player2_won_cards = []
        if room.player2_id:
            for m in moves:
                if (
                    m.resolved
                    and m.winner_user_id == room.player2_id
                    and m.player2_card_id is not None
                ):
                    c = Card.query.get(m.player2_card_id)
                    if c:
                        player2_won_cards.append(card_to_payload(c))

        return jsonify(
            {
                "room": {
                    "room_code": room.room_code,
                    "status": room.status,
                    "player1_score": room.player1_score,
                    "player2_score": room.player2_score,
                    "winner_id": room.winner_id,
                    "player1_username": room.player1.username if room.player1 else None,
                    "player2_username": room.player2.username if room.player2 else None,
                    "winner_username": room.winner.username if room.winner_id else None,
                    # last round display
                    "last_round_player1_card": p1_last_card_payload,
                    "last_round_player2_card": p2_last_card_payload,
                    "last_round_winner_username": last_round_winner_username,
                    # won cards for each player
                    "player1_won_cards": player1_won_cards,
                    "player2_won_cards": player2_won_cards,
                },
                "moves": moves_payload,
            }
        )

    @app.post("/api/rooms/<room_code>/play")
    @auth_required
    def play_card(room_code):
        """
        Play a card into the current round for the authenticated user.

        Expects JSON payload with:
        - card_id (int): ID of a card that must be in the user's active deck.

        The function:
        - Ensures the room is active and the user is part of it.
        - Ensures the card belongs to the user's active deck.
        - Records the card as player1 or player2's choice for the round.
        - If both players have played, resolves the move.

        Args:
            room_code (str): Public code of the room.

        Returns:
            Response: JSON with move status, scores, and room status.
        """
        user = g.current_user
        data = request.get_json() or {}
        card_id = data.get("card_id")

        if not isinstance(card_id, int):
            return jsonify({"error": "card_id must be an integer"}), 400

        room = Room.query.filter_by(room_code=room_code.upper()).first()
        if not room:
            return jsonify({"error": "Room not found"}), 404

        if room.status != "active":
            return (
                jsonify({"error": f"Room is not active (status={room.status})"}),
                400,
            )

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
            # Start a new round
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
            # Fill in the missing side of the current round
            if is_player1:
                if current_move.player1_card_id is not None:
                    return jsonify({"error": "You already played this round"}), 400
                current_move.player1_card_id = card_id
            else:
                if current_move.player2_card_id is not None:
                    return jsonify({"error": "You already played this round"}), 400
                current_move.player2_card_id = card_id
            db.session.commit()

        # Resolve the round if both players have played a card
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