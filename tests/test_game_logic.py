from app import create_app
from cardjitsu.models import db, Card
from flask import current_app

def test_compare_cards_fire_beats_grass(app):
    from app import compare_cards

    with app.app_context():
        fire = Card(element='fire',power=5,colour = 'red', name='Fire 5 Red')
        grass = Card(element='grass',power=10,colour = 'green', name='Grass 10 Green')

        db.session.add_all([fire,grass])
        db.session.commit()

        result = compare_cards(fire, grass)
        assert result == 1  # Fire should beat Grass

def test_compare_cards_grass_beats_water(app):
    from app import compare_cards

    with app.app_context():
        water = Card(element='water',power=5,colour = 'red', name='Water 5 Red')
        grass = Card(element='grass',power=10,colour = 'green', name='Grass 10 Green')

        db.session.add_all([water,grass])
        db.session.commit()

        result = compare_cards(water, grass)
        assert result == 2  # Grass should beat Water

def test_has_club_penguin_win_three_same_element_diff_colours(app):
    from app import has_club_penguin_win

    with app.app_context():
        c1 = Card(element='fire',power=3,colour = 'red', name='Fire 3 Red')
        c2 = Card(element='fire',power=7,colour = 'blue', name='Fire 7 Blue')
        c3 = Card(element='fire',power=10,colour = 'green', name='Fire 10 Green')
        db.session.add_all([c1,c2,c3])
        db.session.commit()

        assert has_club_penguin_win([c1, c2, c3]) is True