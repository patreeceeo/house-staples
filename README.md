# House Staples

The list of staples the house keeps stocked, and the stores we prefer to order
each one from. The house decides what goes on the list by vote; the orderer
keeps this repository up to date.

Live site: https://patreeceeo.github.io/house-staples/

## For housemates

### Searching

Type in the search box to find a staple by name, alias, product or category.
Search tolerates small typos and missing spaces ("oatmilk" finds "Oat Milk").
Use the Store and Category menus to narrow the list, and Sort to group by
category or list by name. Stores for each staple are shown in order of
preference: the first is where we usually order it.

### Proposing a change

To add a staple, remove one, or change its preferred stores, open a new issue
on the [GitHub repo](https://github.com/patreeceeo/house-staples/issues/new/choose)
and pick **Propose a staple** (you need a GitHub account). Fill in the change
type, staple name, preferred stores (one per line, most preferred first) and
your reason.

How the vote works:

- Voting stays open for 7 days or until the next house meeting, whichever
  comes first.
- Vote by reacting to the issue: thumbs up for yes, thumbs down for no.
- The proposal passes with a simple majority of those who vote, as long as at
  least half the house votes.
- If it passes, the orderer updates `data/staples.yaml` and closes the issue.

## For the orderer / maintainer

### Editing staples

Staples live in `data/staples.yaml`, a list of entries:

| Field      | Required | Notes |
|------------|----------|-------|
| `id`       | yes      | Unique, kebab-case (lowercase letters, digits, hyphens), e.g. `oat-milk`. |
| `name`     | yes      | Display name. |
| `category` | yes      | Free text; the site groups and filters by it. Reuse existing categories. |
| `aliases`  | no       | List of other names to match in search. |
| `stores`   | no       | List of store ids from `data/stores.yaml`, most preferred first. No duplicates. |
| `product`  | no       | Specific product or brand. |
| `unit`     | no       | Size or quantity, e.g. `1 gal` or `case of 12`. |

Any other field is rejected. Example:

```yaml
- id: oat-milk
  name: Oat Milk
  category: Dairy & Eggs
  aliases: [oatmilk, oat beverage]
  stores: [costco, restaurant-depot]   # Costco first, Restaurant Depot as fallback
  product: Oatly Barista Edition
  unit: case of 6
```

### Adding a store

Add an entry with `id` (kebab-case) and `name` to `data/stores.yaml`, then
reference its `id` from a staple's `stores` list. Staples can only reference
stores that exist in this file.

```yaml
- id: trader-joes
  name: Trader Joe's
```

### Running locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                         # install dependencies
uv run python -m staples_site.validate          # check data/*.yaml; lists every problem
uv run pytest                                   # run tests
uv run python -m staples_site.build --out dist  # build the site into dist/
```

Then open `dist/index.html` in a browser; it works straight from the file.

### Deploys

The GitHub Actions workflow (`.github/workflows/pages.yml`) validates the data,
runs the tests, builds the site and deploys it to GitHub Pages. It runs on
every push to `main`, weekly on Monday at 13:00 UTC (about 6am Pacific), and on
demand from the Actions tab (Run workflow). If validation or tests fail,
nothing is deployed.

### One-time setup

1. **Settings -> Pages -> Source: GitHub Actions.**
2. Create a label named `staple-proposal` (Issues -> Labels -> New label).
   The issue form applies it to proposals, but GitHub only applies labels that
   already exist in the repository.
