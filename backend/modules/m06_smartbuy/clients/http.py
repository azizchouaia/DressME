"""Real calls to the other modules. Fill in when their APIs exist (same return shapes as mocks)."""

import httpx  # noqa: F401


class HttpClients:
    def classify(self, image):
        raise NotImplementedError("POST M1 /classify")

    def similar(self, user_id, embedding, k):
        raise NotImplementedError("POST M1 /similar")

    def count_type(self, user_id, subcategory):
        raise NotImplementedError("GET M1 /items?subcategory=...")

    def recommend_with(self, user_id, candidate):
        raise NotImplementedError("POST M2 /recommend (locked_items=[candidate])")

    def gaps(self, user_id):
        raise NotImplementedError("GET M5 /profile/{user_id}/gaps")

    def catalogue_search(self, category, colour, max_price):
        raise NotImplementedError("GET M7 /catalogue/search")

    def explain(self, facts):
        raise NotImplementedError("POST M8 /explain")
