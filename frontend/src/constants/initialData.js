export const DEFAULT_SETTINGS = {
  temperature: 0.2,
  top_p: 0.9,
  top_k: 40,
  max_tokens: 2048,
  reranker_top_n: 10,
  model: "cohere/command-a-reasoning",
  stream_mode: "burst",
  provider: "xkiro",
  api_key: "",
  base_url: "https://api.xkiro.com/v1",
  jina_api_key: "",
};

export const SAMPLE_SOURCES_DIABETES = [];

// Cleaned: No dummy chat threads. A fresh session starts with empty threads!
export const INITIAL_THREADS = [];
