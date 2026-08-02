from app.router import HeuristicRouter, build_routing_context


def test_router_sends_greeting_to_small_model() -> None:
    router = HeuristicRouter(large_model="large", small_model="small")
    decision = router.select_model(build_routing_context("hello"))
    assert decision.model == "small"


def test_router_sends_code_to_large_model() -> None:
    router = HeuristicRouter(large_model="large", small_model="small")
    decision = router.select_model(build_routing_context("write python code to parse json"))
    assert decision.model == "large"
