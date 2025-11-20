# Card-Jitsu Web App
Advance Web Dev project, Card-Jitsu simulator

## What is Card-Jitsu?
<p>Card-Jitsu is a simple but strategic card game from Club Penguin.<br>Players battle using cards based on three elements</p>
<ul><li>Fire<li>Grass<li>Snow</ul>
Each card also has a power number (1-12), and a color

### Rules Summary
<ol>
    <li>Elements follow rock-paper-scissors logic
    <ul>
        <li>Fire beats Snow
        <li>Snow beats Grass
        <li>Grass beats Fire
    </ul>
    <li>If both cards are the same element, the higher power number wins
    <li>Players reveal cards simultaneously
    <li>Games proceed through multiple rounds
    <li>A match ends when one player gets either
    <ul>
        <li>A player wins a round with each type of element
        <li>A player wins 3 rounds with different colors of the same element
    </ul>
</ol>

## Projecy Overview
<p>This application recreates the Card-jitsu experience as a full-stack web app using:</p>
<ul>
    <li>Python Flask for backend and API
    <li>SQLAlchemy ORM 
    <li>JWT Authentication for a secure login
    <li>Some External API
    <li>HTML forms for a simple UI
</ul>

## System Architecture
The Style will be Monolithic with MVC-like organization


## How the website works

### Registration

- User enters username, email, password
- Password is hased before storage
- System
    - creates a User
    - assigns 15 random cards (UserCard rows)
    - creates an empty Deck

### Login

- User logs in with username + password
- Backend verifies the hash
- Backend returns a JWT token for authenticated requests

### Viewing Cards

Endpoint: GET api/user/cards

- User sees their 15 assigned cards

### Creating/Editing a Deck

- User selects 10 of their 15 cards
- Simple interface
- Each card displayed with:
    - element
    - power
    - colour
    - "Select"/"Deselect" button
- Backend validates:
    - exactly 10 cards
    - all belong to the user
- Then updates DeckCard rows

### Joining a Room

User enters a room code

Player 1 creates room <br>
<strong>POST api/rooms</strong><br><br>
Player 2 joins room <br>
<strong>POST api/rooms/join</strong><br><br>
Room moves to active status

### Playing the Match

Each Round:<br>
1. Both Players send <strong>POST api/rooms/\<room\>/play{"card_id":123}</strong>
2. When boths moves are in:
    - Backend compares element & power
    - Determines winner using the rules from above
    - Stores the round in Move
3. Scores update
4. When match ends:
    - Room.winner_id filled
    - Status becomes finished


## Data Models

### User

| Attribute     | Type  | Description       |
| :---:         | :---: | :---:             |
| id            | int   | Primary Key       |
| username      | str   | Unique username   |
|password_hash  | str   | Hashed password   |

Relationships:<br>
<ul>
    <li>decks, the users decks
    <li>user_cards, the 15 base cards assigned at registration
    <li>rooms_as_p1, rooms_as_p2, rooms they are participating in
</ul>

### Card

| Attribute     | Type  | Description       |
| :---:         | :---: | :---:             |
|id|int|Primary Key|
|element|str|"fire","water","snow"|
|power|int|1-12|
|colour|str|"red", "blue", "yellow", "green", "purple", "orange"|
|name|str|"fire 12 blue"|

These cards form the global card pool. User recieve 15 random ones

### UserCard

| Attribute     | Type  |
| :---:         | :---: |
|id|int|
|user_id|Foreign Key -> User|
|card_id|Foreign Key -> Card|

This determines which card a user can place in a deck

### Deck

| Attribute     | Type  |
| :---:         | :---: |
|id|int|
|user_id|Foreign Key -> User|
|name|str|
|is_active|bool|
|created_at| DateTime|

A deck of exactly 10 chosen cards

### DeckCard

| Attribute     | Type  |
| :---:         | :---: |
|id|int|
|deck_id|Foreign Key -> Deck|
|card_id|Foreign Key -> Card|

### Room

| Attribute     | Type  | Description       |
| :---:         | :---: | :---:             |
|id|int|Primary Key|
|room_code|str|Code users enter to join|
|player1_id|Foreign Key -> User | First Player|
|player2_id|Foreign Key -> User | Second Player|
|status|str|"waiting","active", "finished"|
|winner_id|Foreign Key -> User | Winner of match|

### Move

| Attribute     | Type  |
| :---:         | :---: |
|id| int|
|room_id|Foreign Key -> Room|
|round_number|int|
|player1_card_id|Foreign Key -> Card|
|player2_card_id|Foreign Key -> Card|
|resolved|bool|
|winner_user_id|Foreign Key -> User|


