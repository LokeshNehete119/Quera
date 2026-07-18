import sys
import os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

def main():
    tables = {
        "users_rich": "id (int), name (varchar), email (varchar)",
        "products_rich": "id (int), name (varchar), price (decimal)",
        "orders_rich": "id (int), user_id (int), order_date (date)",
        "order_items_rich": "order_id (int), product_id (int), quantity (int)",
        "reviews_rich": "id (int), product_id (int), rating (int), comment (text)",
        "suppliers_rich": "id (int), name (varchar)",
        "categories_rich": "id (int), name (varchar)",
        "warehouses_rich": "id (int), location (varchar)",
        "shipments_rich": "id (int), status (varchar)"
    }

    documents = [f"{t} {cols}" for t, cols in tables.items()]
    table_names = list(tables.keys())

    model = SentenceTransformer('all-MiniLM-L6-v2')
    doc_embeddings = model.encode(documents)

    queries = [
        ("Case 11", "who has spent the most money with us"),
        ("Case 16", "Show me the status of the people")
    ]

    for label, q in queries:
        print(f"\n--- {label} ---")
        print(f"Query: '{q}'")
        q_emb = model.encode([q])
        sims = cosine_similarity(q_emb, doc_embeddings).flatten()
        
        results = list(zip(table_names, sims))
        results.sort(key=lambda x: x[1], reverse=True)
        
        for t, s in results:
            print(f"  {t:20s}: {s:.4f}")

if __name__ == "__main__":
    main()
