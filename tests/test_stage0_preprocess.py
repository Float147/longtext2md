from src.pipeline.stage0_preprocess import clean_noise_stage

def test_clean_noise_removes_repeated_fillers():
    result = clean_noise_stage("na ge na ge jiu shi shuo Spring Boot pei zhi")
    assert "Spring Boot" in result

def test_clean_noise_preserves_code_terms():
    result = clean_noise_stage("Write @RestController annotation")
    assert "@RestController" in result

def test_clean_noise_handles_empty():
    assert clean_noise_stage("") == ""
