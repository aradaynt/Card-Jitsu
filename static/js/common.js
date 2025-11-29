function injectNavbar() {
    const placeholder = document.getElementById("navbar-placeholder");
    if (!placeholder) return;

    placeholder.innerHTML = `
        <div class="navbar">
            <div class="navbar-left">
                <span class="navbar-title">Card-Jitsu</span>
                <a href="/home">Home</a>
                <a href="/deckbuilding">Deck Builder</a>
                <a href="/room">Rooms</a>
                <button class="link-button" id="rules-link">Rules</button>
            </div>

            <div class="navbar-right">
                <span id="user-info"></span>
                <button id="logoutbutton" class="btn secondary" style="display:none;">Logout</button>
            </div>
        </div>

        <div id="rules-modal" class="modal hidden">
            <div class="modal-content">
                <button class="modal-close" id="rules-close">&times;</button>

                <h2>What is Card-Jitsu?</h2>
                <p>
                    Card-Jitsu is a simple but strategic card game inspired by Club Penguin.
                    Players battle using cards based on three elements:
                </p>
                <ul>
                    <li>Fire</li>
                    <li>Water</li>
                    <li>Grass</li>
                </ul>
                <p>Each card also has a power number (1–12) and a colour.</p>

                <h3>Rules Summary</h3>
                <ol>
                    <li>
                        Elements follow rock-paper-scissors logic:
                        <ul>
                            <li>Fire beats Grass</li>
                            <li>Grass beats Water</li>
                            <li>Water beats Fire</li>
                        </ul>
                    </li>
                    <li>If both cards are the same element, the higher power number wins.</li>
                    <li>Players reveal cards simultaneously.</li>
                    <li>Games proceed through multiple rounds.</li>
                    <li>
                        A match ends when one player achieves:
                        <ul>
                            <li>One round win with each element (Fire, Water, Grass), or</li>
                            <li>Three round wins using different colours of the same element.</li>
                        </ul>
                    </li>
                </ol>
            </div>
        </div>
    `;
}

function setupAuthUI() {
    const userInfoSpan = document.getElementById("user-info");
    const logoutBtn = document.getElementById("logoutbutton");

    if (!userInfoSpan || !logoutBtn) return;

    const username = localStorage.getItem("username");
    const token = localStorage.getItem("token");

    if (token && username) {
        userInfoSpan.textContent = "Logged in as: " + username;
        logoutBtn.style.display = "inline-block";
    } else {
        userInfoSpan.textContent = "You are not logged in.";
        logoutBtn.style.display = "none";
    }

    logoutBtn.addEventListener("click", () => {
        localStorage.removeItem("token");
        localStorage.removeItem("username");
        window.location.href = "/login";
    });
}

function setupRulesModal() {
    const modal = document.getElementById("rules-modal");
    const openBtn = document.getElementById("rules-link");
    const closeBtn = document.getElementById("rules-close");

    if (!modal || !openBtn || !closeBtn) return;

    openBtn.addEventListener("click", () => {
        modal.classList.remove("hidden");
    });

    closeBtn.addEventListener("click", () => {
        modal.classList.add("hidden");
    });

    modal.addEventListener("click", (e) => {
        if (e.target === modal) {
            modal.classList.add("hidden");
        }
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            modal.classList.add("hidden");
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    injectNavbar();
    setupAuthUI();
    setupRulesModal();
});