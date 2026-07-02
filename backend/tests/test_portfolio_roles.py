from app.portfolio.roles import derive_portfolio_profile, load_portfolio_role_config


def test_default_portfolio_role_config_derives_core_satellite_roles() -> None:
    config = load_portfolio_role_config()

    profile = derive_portfolio_profile(
        label_codes={
            "alpha_positive",
            "beta_low",
            "data_sufficient",
            "fee_low",
            "information_ratio_high",
            "manager_tenure_long",
            "quality_growth",
        },
        active_label_codes={"quality_growth"},
        group_codes={"active_equity_candidate_pool"},
        classifications={"management_style": "active"},
        review_action="observe",
        config=config,
    )

    assert profile["allocation_status"] == "eligible"
    assert "core_holding_candidate" in profile["portfolio_roles"]
    assert "satellite_alpha" in profile["portfolio_roles"]
    assert "defensive_anchor" in profile["portfolio_roles"]
    assert "low_cost" in profile["portfolio_roles"]
    assert "style_quality_growth" in profile["portfolio_roles"]
    assert profile["style_tags"] == ["quality_growth"]
    assert profile["return_tags"] == ["alpha_positive", "information_ratio_high"]


def test_portfolio_role_config_marks_data_gap_as_review_required() -> None:
    config = load_portfolio_role_config()

    profile = derive_portfolio_profile(
        label_codes={"data_insufficient", "manual_review_required"},
        active_label_codes=set(),
        group_codes={"data_gap_pool"},
        classifications={"calculation_eligibility": "data_gap"},
        review_action="manual_review",
        config=config,
    )

    assert profile["allocation_status"] == "review_required"
    assert profile["portfolio_roles"] == ["needs_review"]
    assert profile["blocking_reasons"] == [
        "data_insufficient",
        "manual_review_action",
        "manual_review_required",
    ]


def test_index_tool_role_accepts_group_or_classification() -> None:
    config = load_portfolio_role_config()

    from_group = derive_portfolio_profile(
        label_codes={"data_sufficient"},
        active_label_codes=set(),
        group_codes={"passive_tool_pool"},
        classifications={},
        review_action="observe",
        config=config,
    )
    from_classification = derive_portfolio_profile(
        label_codes={"data_sufficient"},
        active_label_codes=set(),
        group_codes=set(),
        classifications={"management_style": "passive_index"},
        review_action="observe",
        config=config,
    )

    assert "index_tool" in from_group["portfolio_roles"]
    assert "index_tool" in from_classification["portfolio_roles"]
