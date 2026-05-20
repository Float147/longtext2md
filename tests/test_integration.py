from src.utils.text_utils import clean_noise
from src.chunking.boundary_detector import detect_boundaries

def test_full_text_pipeline_no_llm():
    text = "We will learn about Spring Boot autoconfiguration.\n\nFirst create a config class with @Configuration annotation.\n\nNext we talk about conditional assembly. @ConditionalOnClass is the core.\n\nLet's write some code.\npublic class MyConfig {\n    @Bean\n    public DataSource dataSource() { return new HikariDataSource(); }\n}\nLet's run it and see."
    cleaned = clean_noise(text)
    assert "Spring Boot" in cleaned
    assert cleaned.count("\n\n\n") == 0
    chunks = detect_boundaries(cleaned, max_chars=300)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 300