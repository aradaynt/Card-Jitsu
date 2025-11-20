from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    decks = db.relationship( "Deck", back_populates="user", cascade="all, delete-orphan")
    user_cards = db.relationship( "UserCard", back_populates="user", cascade="all, delete-orphan")
    rooms_as_p1 = db.relationship("Room", back_populates="player1", foreign_keys="Room.player1_id")
    rooms_as_p2 = db.relationship("Room", back_populates="player2", foreign_keys="Room.player2_id")
    

    def set_password(self, raw_password: str) -> None:
        """Hash and store the user's password."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class Card(db.Model):
    """Base card definition: element + power."""

    __tablename__ = "cards"

    id = db.Column(db.Integer, primary_key=True)
    element = db.Column(db.String(16), nullable=False)  # "fire", "water", "snow"
    power = db.Column(db.Integer, nullable=False)        # e.g., 1–12
    colour = db.Column(db.String(16), nullable=True)  
    name = db.Column(db.String(64), nullable=False)


    def __repr__(self) -> str:
        return f"<Card id={self.id} {self.element} {self.power}>"


class UserCard(db.Model):
    """Cards owned by a specific user (their collection of 15 cards)."""

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
    """A deck built by a user (10 chosen cards)."""

    __tablename__ = "decks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(64), nullable=False, default="Main Deck")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(), nullable=False)

    user = db.relationship("User", back_populates="decks")
    cards = db.relationship("DeckCard", back_populates="deck", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Deck id={self.id} user_id={self.user_id} name={self.name!r}>"


class DeckCard(db.Model):
    """Join table between Deck and Card (10 rows per deck)."""

    __tablename__ = "deck_cards"
    __table_args__ = (UniqueConstraint("deck_id", "card_id", name="uq_deck_card"))

    id = db.Column(db.Integer, primary_key=True)
    deck_id = db.Column(db.Integer, db.ForeignKey("decks.id"), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)

    deck = db.relationship("Deck", back_populates="cards")
    card = db.relationship("Card")

    def __repr__(self) -> str:
        return f"<DeckCard deck_id={self.deck_id} card_id={self.card_id}>"
    
class Room(db.Model):
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(16), unique=True, nullable=False)
    player1_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    status = db.Column(db.String(16), default="waiting", nullable=False)  # "waiting", "active", "finished"

    created_at = db.Column(db.DateTime, default=datetime.now(), nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    player1_score = db.Column(db.Integer, default=0, nullable=False)
    player2_score = db.Column(db.Integer, default=0, nullable=False)

    winner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    player1 = db.relationship("User", back_populates="rooms_as_p1", foreign_keys=[player1_id])
    player2 = db.relationship("User", back_populates="rooms_as_p2", foreign_keys=[player2_id])
    moves = db.relationship("Move", back_populates="room", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Room id={self.id} room_code={self.room_code!r} status={self.status!r}>"
    

class Move(db.Model):
    __tablename__ = "moves"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)

    player1_card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)
    player2_card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)

    resolved = db.Column(db.Boolean, default=False, nullable=False)
    winner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now(), nullable=False)

    room = db.relationship("Room", back_populates="moves")
    player1_card = db.relationship("Card", foreign_keys=[player1_card_id])
    player2_card = db.relationship("Card", foreign_keys=[player2_card_id])
    winner = db.relationship("User", foreign_keys=[winner_user_id])

    def __repr__(self) -> str:
        return(
            f"<Move room_id={self.room_id} round={self.round_number} "
            f"resolved={self.resolved}>"
        )


def seed_cards(session=None) -> None:
    if session is None:
        session = db.session
    if session.query(Card).count() > 0:
        return
    elements = ["fire", "water", "snow"]
    colours = ["red", "blue", "yellow", "green", "purple", "orange"]
    for element in elements:
        for power in range(1,13):
            colour = colours[(power - 1) % len(colours)]
            session.add(
            Card(
                element = element,
                power = power,
                colour = colour,
                name = f"{element.title()} {power} {colour.title()}",
                )
            )
    session.commit()

