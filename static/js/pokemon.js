// static/js/pokemon.js
// Helpers for mapping card element + power -> Pokémon sprite via PokéAPI

// Pools of Pokémon by element + "stage"
// 1–3  = basic
// 4–6  = stage1
// 7–10 = stage2
// 11+  = legendary
const PokemonPools = {
    fire: {
        basic:     ["charmander", "vulpix", "torchic"],
        stage1:    ["charmeleon", "ninetales", "combusken"],
        stage2:    ["charizard", "blaziken", "arcanine"],
        legendary: ["moltres", "entei", "heatran"]
    },
    water: {
        basic:     ["squirtle", "psyduck", "piplup"],
        stage1:    ["wartortle", "golduck", "prinplup"],
        stage2:    ["blastoise", "empoleon", "gyarados"],
        legendary: ["suicune", "kyogre", "palkia"]
    },
    grass: {
        basic:     ["bulbasaur", "oddish", "treecko"],
        stage1:    ["ivysaur", "gloom", "grovyle"],
        stage2:    ["venusaur", "sceptile", "victreebel"],
        legendary: ["celebi", "shaymin", "virizion"]
    }
};

function getPowerTier(power) {
    if (power <= 3) return "basic";
    if (power <= 6) return "stage1";
    if (power <= 10) return "stage2";
    return "legendary";
}

// Deterministic pick from the pool based on power (simple but consistent)
function pickPokemonName(element, power) {
    const elemKey = (element || "").toLowerCase();
    const tier = getPowerTier(power);
    const pools = PokemonPools[elemKey];
    if (!pools) return null;

    const pool = pools[tier];
    if (!pool || !pool.length) return null;

    const index = power % pool.length;
    return pool[index];
}

// Cache to avoid hitting PokéAPI repeatedly for same Pokémon
const spriteCache = {};

async function fetchPokemonSpriteUrl(name) {
    const key = name.toLowerCase();
    if (spriteCache[key]) {
        return spriteCache[key];
    }

    const resp = await fetch(`https://pokeapi.co/api/v2/pokemon/${key}`);
    if (!resp.ok) {
        console.error("Failed to fetch Pokémon", name);
        return null;
    }

    const data = await resp.json();
    const url =
        data.sprites?.other?.["official-artwork"]?.front_default ||
        data.sprites?.front_default ||
        null;

    spriteCache[key] = url;
    return url;
}

// Public helper to add a Pokémon sprite to a card tile
function addPokemonSpriteToCard(card, tile) {
    const pokemonName = pickPokemonName(card.element, card.power);
    if (!pokemonName) return;

    const spriteContainer = document.createElement("div");
    spriteContainer.className = "card-sprite";

    const img = document.createElement("img");
    img.alt = pokemonName;
    img.loading = "lazy";

    spriteContainer.appendChild(img);
    // Put sprite at the top of the card
    tile.insertBefore(spriteContainer, tile.firstChild);

    fetchPokemonSpriteUrl(pokemonName)
        .then((url) => {
            if (url) {
                img.src = url;
            } else {
                spriteContainer.remove();
            }
        })
        .catch((err) => {
            console.error("Error loading sprite:", err);
            spriteContainer.remove();
        });
}