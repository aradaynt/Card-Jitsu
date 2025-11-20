from flask import Flask
from cardjitsu.models import db, seed_cards


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cardjitsu.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        #seeding the cards table once
        seed_cards()

    #test route 
    @app.route("/")
    def index():
        return "Card-Jitsu backend is running!"

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
