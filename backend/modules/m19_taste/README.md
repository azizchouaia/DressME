# M19 · Taste

**Owner:** BO8 · **Tool name:** `taste`

Taste ranks an outfit or a purchase from one person's memory. Every user shares the FashionCLIP model. The memory is rows for that `user_id`: likes, dislikes, and saves.

Call it first when the person wants an outfit or a purchase. Stylist and smartbuy can follow from `next_actions`. Talk reads this same memory when it explains a score.

`POST /m19/run` with `user_id`, `purpose` (`outfit` or `buy`), and `candidates`. A `kind` of like, dislike, skip, or save records a preference.

A score returned here stays as returned.
