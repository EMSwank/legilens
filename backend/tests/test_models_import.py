def test_models_importable():
    from app.models.bill import Bill
    from app.models.minhash_signature import MinHashSignature
    from app.models.ist_score import ISTScore
    from app.models.similarity_match import SimilarityMatch
    from app.models.friction_tag import FrictionTag
    assert Bill.__tablename__ == "bills"
    assert MinHashSignature.__tablename__ == "minhash_signatures"
