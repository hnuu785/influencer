from app.seed_ai_virtual_influencers import load_seed_profiles


def test_seed_profiles_are_unique_and_source_labeled():
    profiles = load_seed_profiles()

    assert len(profiles) >= 20
    assert len({profile.profile_id for profile in profiles}) == len(profiles)
    assert len({profile.profile_url for profile in profiles}) == len(profiles)
    assert all(profile.platform == "instagram" for profile in profiles)
    assert all(profile.source == "public_research" for profile in profiles)
    assert all(
        profile.source_fields["metric_type"]
        == "third_party_public_snapshot"
        for profile in profiles
    )
    assert all(
        profile.source_fields["direct_instagram_fetch"] == "not_attempted"
        for profile in profiles
    )


def test_seed_profiles_keep_snapshot_provenance():
    profiles = {profile.username: profile for profile in load_seed_profiles()}

    miquela = profiles["lilmiquela"]
    assert miquela.follower_count == 2_272_412
    assert miquela.source_fields["observed_at"] == "2026-07-18"
    assert miquela.source_fields["confidence"] == "high"
    assert miquela.source_fields["source_url"].startswith("https://")

    stale_profile = profiles["gioalemann"]
    assert stale_profile.source_fields["confidence"] == "stale"
