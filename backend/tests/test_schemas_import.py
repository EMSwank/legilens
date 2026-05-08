def test_schemas_importable():
    from app.schemas.bill import BillListItem, BillDetail, ISTScoreOut
    from app.schemas.match import MatchOut, SnippetItem, GhostMessage
    from app.schemas.stats import StatsOut, TagCountOut
    assert BillDetail.model_fields["id"]
