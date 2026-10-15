# AI Usage

> DRAFT: review every line, correct anything that doesn't match what you actually did,
> and fill in the sections marked TODO in your own words before submitting.

## 1. Tools used

- Claude (Anthropic), via the claude.ai chat interface.
- TODO: list any other tools you used (or delete this line).

## 2. Prompts I gave

Summarised in order (the full text is in `chat_transcript` in this repo):

1. Uploaded the assignment document and asked for help understanding the requirements.
2. Asked for naming suggestions for the app.
3. Shared my first models and asked for indexes on `Box` (max weight, max volume, cost) and for order total weight and volume calculation.
4. Asked for the API and test cases.
5. Shared updated models and asked to update the order total calculation.
6. Asked for indexes on the order models.
7. Shared the near-final models and asked for `views.py`, `urls.py`, `tests.py` (Django `TestCase`) and `services.py` to fulfil the requirements.
8. Asked to remove unnecessary code and comments and anything not in the requirements.
9. Asked for the supporting submission files (README, CI, etc.).

## 3. Output I accepted

- The service-layer structure (selection logic separate from views).
- Storing `Box.max_volume` as a computed database column so it can be indexed, instead of a property.
- The `UniqueConstraint(order, product)` on `OrderItem`.
- The per-item dimension check (sort dimensions and compare), in addition to the volume check.
- Splitting `Order` into `Order` and `OrderItem` so an order can hold several products.
- The test suite structure and the API status codes (200/400/404/405/422).
- TODO: add anything else you accepted as-is.

## 4. Output I rejected or modified

- Trimmed the generated code: removed `Order.total_weight` / `total_volume` properties, `OrderItem.line_weight` / `line_volume`, the `Order` index on `created_at`, extra API response fields, and several low-value tests.
- Changed the first suggestion for order totals (a database-side aggregate) to plain Python `Decimal` arithmetic.
- TODO: describe other changes you made yourself, for example edits to field sizes, names or logic, and why.

## 5. Mistakes found

Mistakes in my own code, caught by the AI during review:

- `def __dec(...)` used a double-underscore name. Python's name mangling would raise a `NameError` inside the class body. Fixed by renaming to `_dec`.
- `_dec(digit=20, place=6)` used the wrong keyword names (`places`, not `place`). Would have raised a `TypeError`.
- When I edited the `Box` model, `cost`, `length`, `width` and `height` were dropped while indexes and `candidates()` still used them, and `candidates()` filtered on `volume__gte` after the field was renamed to `max_volume`. Would have failed Django's checks or raised a `FieldError`.
- `max_digits=20` on `max_volume` could overflow for very large boxes. Raised to 26.

Mistakes or weak spots in the AI's output:

- The first version of the AI's code used an `explain()` test named as if it verified index usage; it only checked the query could run, so it was removed.
- The first version of the AI's order-totals code used a database aggregate that was replaced with Python `Decimal` sums.
- The AI's first test suite referenced `box.volume` after I renamed the field to `max_volume`, so a test needed updating.
- Early code written before the model changes would not have run against the final models without fixes.
- TODO: add any other mistakes you personally noticed.

## 6. How I verified the final code

- Ran `python manage.py test -v 2` (37 tests passing; output in `TEST_OUTPUT.md`, also run in GitHub Actions).
- Ran `python manage.py makemigrations --check` to confirm models and migrations match.
- Read through each function and checked the selection rules by hand against the tests: exact weight/volume boundaries, rotation, cost ties, and fallback to the next box when the cheapest fails the dimension check.
- TODO: describe any manual checks you did, such as calling the API with curl and adding data in the admin.
