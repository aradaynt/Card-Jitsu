"""
models.py
---------
Database models for the Card-Jitsu web application.

This module defines all SQLAlchemy ORM models used in the system,
including users, cards, decks, rooms, and gameplay moves.

These models form the core data layer of the application and are used by
the API routes and game logic to store and retrieve persistent data.
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()

class User(db.Model):
    """
    Represents a registered user in the system.

    Attributes:
        username (str): Unique account name.
        password_hash (str): Hashed password.
        win_count (int): Total wins recorded.
        total_games (int): Total games played.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    win_count = db.Column(db.Integer, default=0, nullable=False)
    total_games = db.Column(db.Integer, default=0, nullable=False)

    # Relationships
    decks = db.relationship(
        "Deck",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    user_cards = db.relationship(
        "UserCard",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    rooms_as_p1 = db.relationship(
        "Room",
        back_populates="player1",
        foreign_keys="Room.player1_id",
    )
    rooms_as_p2 = db.relationship(
        "Room",
        back_populates="player2",
        foreign_keys="Room.player2_id",
    )

    def set_password(self, raw_password: str) -> None:
        """
        Hash a plaintext password and store it on the user.
        """
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """
        Verify a plaintext password against the stored hash.

        Returns:
            bool: True if the password matches, False otherwise.
        """
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"

class Card(db.Model):
    """
    Represents a base card in the game.

    Cards are defined by:
        - element: fire / water / grass
        - power: 1 to 12
        - colour: "red", "blue", "yellow", "green", "purple", "orange"
    """

    __tablename__ = "cards"

    id = db.Column(db.Integer, primary_key=True)
    element = db.Column(db.String(16), nullable=False)  # "fire", "water", "grass"
    power = db.Column(db.Integer, nullable=False)       # e.g., 1 to 12
    colour = db.Column(db.String(16), nullable=True)    # "red", "blue", "yellow", "green", "purple", "orange"
    name = db.Column(db.String(64), nullable=False)

    def to_dict(self) -> dict:
        """
        Convert card fields into a simple dictionary for API responses.
        """
        return {
            "id": self.id,
            "element": self.element,
            "power": self.power,
            "colour": self.colour,
            "name": self.name,
        }

    def __repr__(self) -> str:
        return f"<Card id={self.id} {self.element} {self.power}>"

class UserCard(db.Model):
    """
    Represents a single card owned by a user.

    Each row links one user to one specific card. The collection size
    (e.g., 40 selectable cards) is controlled by game logic, not by this model.
    """

    __tablename__ = "user_cards"
    __table_args__ = (
        UniqueConstraint("user_id", "card_id", name="uq_user_card"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)

    user = db.relationship("User", back_populates="user_cards")
    card = db.relationship("Card")

    def __repr__(self) -> str:
        return f"<UserCard user_id={self.user_id} card_id={self.card_id}>"

class Deck(db.Model):
    """
    Represents a deck created by a user.

    In our current rules, each deck contains 25 cards chosen from the
    user's available pool (e.g., 40 selectable cards in the deck builder).
    The exact count is enforced in the deck-building logic, not here.
    """

    __tablename__ = "decks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(64), nullable=False, default="Main Deck")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User", back_populates="decks")
    cards = db.relationship(
        "DeckCard",
        back_populates="deck",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Deck id={self.id} user_id={self.user_id} name={self.name!r}>"

class DeckCard(db.Model):
    """
    Join table linking Deck and Card.

    Each deck has one DeckCard row per card in the deck
    (25 DeckCard rows for a full deck under the rules).
    """

    __tablename__ = "deck_cards"
    __table_args__ = (
        UniqueConstraint("deck_id", "card_id", name="uq_deck_card"),
    )

    id = db.Column(db.Integer, primary_key=True)
    deck_id = db.Column(db.Integer, db.ForeignKey("decks.id"), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)

    deck = db.relationship("Deck", back_populates="cards")
    card = db.relationship("Card")

    def __repr__(self) -> str:
        return f"<DeckCard deck_id={self.deck_id} card_id={self.card_id}>"

class Room(db.Model):
    """
    Represents a multiplayer game room.

    Handles:
        - player slots (player 1 / player 2)
        - room status (waiting / active / finished)
        - scoring and winner tracking
        - relationship to Move records
    """

    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(16), unique=True, nullable=False)
    player1_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # "waiting", "active", "finished"
    status = db.Column(
        db.String(16),
        default="waiting",
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    player1_score = db.Column(db.Integer, default=0, nullable=False)
    player2_score = db.Column(db.Integer, default=0, nullable=False)

    winner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    winner = db.relationship("User", foreign_keys=[winner_id])

    player1 = db.relationship(
        "User",
        back_populates="rooms_as_p1",
        foreign_keys=[player1_id],
    )
    player2 = db.relationship(
        "User",
        back_populates="rooms_as_p2",
        foreign_keys=[player2_id],
    )
    moves = db.relationship(
        "Move",
        back_populates="room",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        """
        Serialize room metadata and the most recent round's cards.

        Returns:
            dict: JSON-safe representation used by API routes.
        """
        from .models import Move  # local import to avoid circular references

        base = {
            "room_code": self.room_code,
            "status": self.status,
            "player1_username": self.player1.username if self.player1 else None,
            "player2_username": self.player2.username if self.player2 else None,
            "player1_score": self.player1_score,
            "player2_score": self.player2_score,
            "winner_username": self.winner.username if self.winner else None,
        }

        # Get the latest move in this room (highest ID)
        last_move = (
            Move.query
            .filter_by(room_id=self.id)
            .order_by(Move.id.desc())
            .first()
        )

        def card_to_dict(card: Card | None) -> dict | None:
            """
            Helper to safely convert a Card object to a dict.
            """
            if card is None:
                return None
            return card.to_dict()

        if last_move:
            base["last_round_player1_card"] = card_to_dict(last_move.player1_card)
            base["last_round_player2_card"] = card_to_dict(last_move.player2_card)
        else:
            base["last_round_player1_card"] = None
            base["last_round_player2_card"] = None

        return base

    def __repr__(self) -> str:
        return (
            f"<Room id={self.id} room_code={self.room_code!r} "
            f"status={self.status!r}>"
        )

class Move(db.Model):
    """
    Represents a single round of play in a room.

    Stores both players' selected cards and whether the move is resolved.
    """

    __tablename__ = "moves"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)

    player1_card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=True)
    player2_card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=True)

    resolved = db.Column(db.Boolean, default=False, nullable=False)
    winner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    room = db.relationship("Room", back_populates="moves")
    player1_card = db.relationship("Card", foreign_keys=[player1_card_id])
    player2_card = db.relationship("Card", foreign_keys=[player2_card_id])
    winner = db.relationship("User", foreign_keys=[winner_user_id])

    def __repr__(self) -> str:
        return (
            f"<Move room_id={self.room_id} round={self.round_number} "
            f"resolved={self.resolved}>"
        )

def seed_cards(session=None) -> None:
    """
    Populate the database with the full card list if empty.

    Cards are generated for:
        - 3 elements: fire, water, grass
        - 12 power levels each
        - 6 colours each

    This results in 3 × 12 × 6 = 216 total base cards.
    """
    if session is None:
        session = db.session

    # Avoid seeding twice
    if session.query(Card).count() > 0:
        return

    elements = ["fire", "water", "grass"]
    colours = ["red", "blue", "yellow", "green", "purple", "orange"]

    for element in elements:
        for power in range(1, 13):  # 12 power levels
            for colour in colours:  # 6 colours for each
                session.add(
                    Card(
                        element=element,
                        power=power,
                        colour=colour,
                        name=f"{element.title()} {power} {colour.title()}",
                    )
                )

    session.commit()