from src.utils.text_utils import clean_noise
from src.chunking.boundary_detector import detect_boundaries
from src.utils.toc_generator import generate_toc, insert_toc
from src.utils.mindmap import generate_mindmap

def test_full_text_pipeline_no_llm():
    text = "We will learn about Spring Boot autoconfiguration.\n\nFirst create a config class with @Configuration annotation.\n\nNext we talk about conditional assembly. @ConditionalOnClass is the core.\n\nLet's write some code.\npublic class MyConfig {\n    @Bean\n    public DataSource dataSource() { return new HikariDataSource(); }\n}\nLet's run it and see."
    cleaned = clean_noise(text)
    assert "Spring Boot" in cleaned
    assert cleaned.count("\n\n\n") == 0
    chunks = detect_boundaries(cleaned, max_chars=300)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 300

def test_toc_and_mindmap():
    md = "# Spring Boot\n## Autoconfiguration\n### @ConditionalOnClass\nCore annotation for conditional assembly.\n## Database Integration\n### MyBatis-Plus Config"
    toc = generate_toc(md)
    assert "Autoconfiguration" in toc
    assert "MyBatis-Plus Config" in toc
    mm = generate_mindmap(md, "Spring Boot")
    assert "mindmap" in mm
    assert "Autoconfiguration" in mm
    full = insert_toc(md)
    assert "Table of Contents" in full
