from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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
    cards = db.relationship(
        "DeckCard",
        back_populates="deck",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Deck id={self.id} user_id={self.user_id} name={self.name!r}>"


class DeckCard(db.Model):
    """Join table between Deck and Card (10 rows per deck)."""

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


def seed_cards():
    if session is None:
        session = db.session
    if session.query(Card).count() > 0:
        return
    elements = ["fire", "water", "snow"]
    for element in elements:
        for power in range(1,13):
            Card(
                element = element,
                power = power,
                name = f"{element.title()} {power}",
            )
