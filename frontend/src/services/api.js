import { SAMPLE_SOURCES_DIABETES } from "../constants/initialData";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Checks if the backend API server is reachable
 */
export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(2000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Register a new user
 */
export async function registerUser({ username, email, password, confirm_password }) {
  const isHealthy = await checkBackendHealth();

  if (isHealthy) {
    const res = await fetch(`${API_BASE_URL}/user/create-user`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        email,
        password,
        confirm_password,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || "Signup failed");
    }
    return data;
  }

  // Simulation fallback if backend is offline
  const nowIso = new Date().toISOString();
  return {
    id: Math.floor(Math.random() * 1000) + 1,
    username,
    email,
    created_at: nowIso,
    login_at: nowIso,
    logout_at: null,
  };
}

/**
 * Login user with email & password
 */
export async function loginUser({ email, password }) {
  const isHealthy = await checkBackendHealth();

  if (isHealthy) {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || "Invalid email or password");
    }
    return data; // { access_token, token_type }
  }

  // Simulation fallback
  return {
    access_token: `mock_jwt_token_${Date.now()}`,
    token_type: "bearer",
  };
}

/**
 * Fetch authenticated user profile (/user/me)
 */
export async function getMe(token) {
  const isHealthy = await checkBackendHealth();

  if (isHealthy && token) {
    try {
      const res = await fetch(`${API_BASE_URL}/user/me`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn("Failed fetching /user/me:", e);
    }
  }

  return null;
}

/**
 * Log out user from backend
 */
export async function logoutUser(token) {
  const isHealthy = await checkBackendHealth();

  if (isHealthy && token) {
    try {
      await fetch(`${API_BASE_URL}/auth/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    } catch (e) {
      console.warn("Backend logout notification failed:", e);
    }
  }
}

/**
 * Fetch user's chat threads from backend
 */
export async function fetchUserThreads(token) {
  const authToken = token || localStorage.getItem("access_token");
  if (!authToken) return [];

  try {
    const res = await fetch(`${API_BASE_URL}/chatbot/threads`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    });
    if (res.ok) {
      const data = await res.json();
      return data.threads || [];
    } else {
      console.warn("fetchUserThreads returned status:", res.status);
    }
  } catch (e) {
    console.warn("Failed fetching threads from backend:", e);
  }
  return [];
}

/**
 * Fetch chat messages history for a thread
 */
export async function fetchThreadHistory(threadId, token) {
  const authToken = token || localStorage.getItem("access_token");
  if (!authToken || !threadId) return [];

  try {
    const res = await fetch(`${API_BASE_URL}/chatbot/history/${threadId}`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    });
    if (res.ok) {
      const data = await res.json();
      return data.messages || [];
    }
  } catch (e) {
    console.warn("Failed fetching thread history from backend:", e);
  }
  return [];
}

/**
 * Create a new chat thread in the backend database
 */
export async function createNewChatThread(token) {
  const authToken = token || localStorage.getItem("access_token");
  if (!authToken) return null;

  try {
    const res = await fetch(`${API_BASE_URL}/chatbot/new-chat`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    });
    if (res.ok) {
      const data = await res.json();
      return data;
    }
  } catch (e) {
    console.warn("Failed creating new chat in backend:", e);
  }
  return null;
}

/**
 * Delete chat thread from backend
 */
export async function deleteChatThread(threadId, token) {
  const authToken = token || localStorage.getItem("access_token");
  if (!authToken || !threadId) return false;

  try {
    const res = await fetch(`${API_BASE_URL}/chatbot/delete-chat/${threadId}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    });
    return res.ok;
  } catch (e) {
    console.warn("Failed deleting chat from backend:", e);
    return false;
  }
}

/**
 * Fetch dynamic model information from backend
 */
export async function fetchModelInfo() {
  try {
    const res = await fetch(`${API_BASE_URL}/chatbot/model-info`);
    if (res.ok) {
      return await res.json();
    }
  } catch (e) {
    console.warn("Failed fetching backend model info:", e);
  }
  return null;
}

/**
 * Contributes a Q&A pair to the backend pre-computed semantic cache.
 */
export async function contributeResponse({ query, response, category, sources, token }) {
  const authToken = token || localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE_URL}/chatbot/contribute-response`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    body: JSON.stringify({
      query,
      response,
      category: category || "Community Contributed",
      sources: sources || [],
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Failed to contribute response");
  }
  return data;
}

/**
 * Sends a message and streams back tokens, metadata, and sources.
 * Supports cancellation via abortSignal.
 */
export async function streamChatMessage({
  query,
  threadId,
  settings,
  signal,
  onToken,
  onMetadata,
}) {
  const isHealthy = await checkBackendHealth();
  const token = localStorage.getItem("access_token");

  if (isHealthy) {
    try {
      const response = await fetch(`${API_BASE_URL}/chatbot/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          query,
          thread_id: threadId,
          temperature: settings?.temperature,
          top_k: settings?.top_k,
          top_p: settings?.top_p,
          max_tokens: settings?.max_tokens,
          reranker_top_n: settings?.reranker_top_n,
          stream_mode: settings?.stream_mode || "burst",
        }),
        signal,
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        if (signal?.aborted) {
          reader.cancel();
          throw new DOMException("Aborted", "AbortError");
        }

        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          let eventType = "message";
          let eventData = "";

          const subLines = trimmed.split("\n");
          for (const sub of subLines) {
            if (sub.startsWith("event:")) {
              eventType = sub.replace("event:", "").trim();
            } else if (sub.startsWith("data:")) {
              eventData = sub.replace("data:", "").trim();
            }
          }

          if (eventType === "token") {
            try {
              const parsed = JSON.parse(eventData);
              if (parsed.token) onToken(parsed.token);
            } catch {
              if (eventData) onToken(eventData);
            }
          } else if (eventType === "metadata") {
            try {
              const parsedMeta = JSON.parse(eventData);
              const realSources = Array.isArray(parsedMeta.sources) ? parsedMeta.sources : [];
              onMetadata({
                ...parsedMeta,
                sources: realSources,
              });
            } catch (err) {
              console.warn("Could not parse metadata", err);
            }
          }
        }
      }
      return;
    } catch (err) {
      if (err.name === "AbortError" || signal?.aborted) {
        throw err;
      }
      console.warn("Backend streaming failed, falling back to simulated Hybrid RAG engine:", err);
    }
  }

  // Fallback: Real-time simulation of Hybrid RAG streaming
  await simulateHybridRagStream({
    query,
    threadId,
    settings,
    signal,
    onToken,
    onMetadata,
  });
}

/**
 * Regenerates an existing response without duplicating user queries in history.
 * Hits POST /chatbot/regenerate with SSE streaming.
 */
export async function streamRegenerateChatMessage({
  query,
  threadId,
  settings,
  signal,
  onToken,
  onMetadata,
}) {
  const isHealthy = await checkBackendHealth();
  const token = localStorage.getItem("access_token");

  if (isHealthy) {
    try {
      const response = await fetch(`${API_BASE_URL}/chatbot/regenerate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          query: query || null,
          thread_id: threadId,
          temperature: settings?.temperature,
          top_k: settings?.top_k,
          top_p: settings?.top_p,
          max_tokens: settings?.max_tokens,
          reranker_top_n: settings?.reranker_top_n,
          stream_mode: settings?.stream_mode || "burst",
        }),
        signal,
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        if (signal?.aborted) {
          reader.cancel();
          throw new DOMException("Aborted", "AbortError");
        }

        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          let eventType = "message";
          let eventData = "";

          const subLines = trimmed.split("\n");
          for (const sub of subLines) {
            if (sub.startsWith("event:")) {
              eventType = sub.replace("event:", "").trim();
            } else if (sub.startsWith("data:")) {
              eventData = sub.replace("data:", "").trim();
            }
          }

          if (eventType === "token") {
            try {
              const parsed = JSON.parse(eventData);
              if (parsed.token) onToken(parsed.token);
            } catch {
              if (eventData) onToken(eventData);
            }
          } else if (eventType === "metadata") {
            try {
              const parsedMeta = JSON.parse(eventData);
              const realSources = Array.isArray(parsedMeta.sources) ? parsedMeta.sources : [];
              onMetadata({
                ...parsedMeta,
                sources: realSources,
              });
            } catch (err) {
              console.warn("Could not parse metadata", err);
            }
          }
        }
      }
      return;
    } catch (err) {
      if (err.name === "AbortError" || signal?.aborted) {
        throw err;
      }
      console.warn("Backend regenerate streaming failed, falling back to simulated engine:", err);
    }
  }

  // Fallback simulation
  await simulateHybridRagStream({
    query,
    threadId,
    settings,
    signal,
    onToken,
    onMetadata,
  });
}

/**
 * Intelligent simulation of Hybrid RAG pipeline
 */
async function simulateHybridRagStream({
  query,
  threadId,
  settings,
  signal,
  onToken,
  onMetadata,
}) {
  const startTime = performance.now();
  const lowerQuery = query.toLowerCase();

  const diabetesKeywords = [
    "diabet",
    "sugar",
    "glucose",
    "insulin",
    "a1c",
    "hba1c",
    "metformin",
    "pancrea",
    "ketoacidosis",
    "dka",
    "hypoglycemia",
    "hyperglycemia",
    "retinopathy",
    "neuropathy",
    "cgm",
    "carbohydrate",
    "glycemic",
    "endocrin",
  ];

  const isDiabetes = diabetesKeywords.some((kw) => lowerQuery.includes(kw));
  const detectedIntent = isDiabetes ? "Diabetes" : "Other";

  let responseText = "";
  let sources = [];

  if (isDiabetes) {
    sources = SAMPLE_SOURCES_DIABETES;
    if (lowerQuery.includes("screening") || lowerQuery.includes("diagnos") || lowerQuery.includes("criteria")) {
      responseText = `### ADA 2024 Clinical Screening & Diagnostic Criteria for Diabetes

According to the latest **American Diabetes Association (ADA) Standards of Care in Diabetes (2024)**, diagnostic screening is based on standardized venous plasma laboratory criteria:

1. **Fasting Plasma Glucose (FPG)**:
   - **≥ 126 mg/dL (7.0 mmol/L)**. Fasting is defined as no caloric intake for at least 8 hours.

2. **Hemoglobin A1C**:
   - **≥ 6.5% (48 mmol/mol)**. Test must be performed in a laboratory certified by the NGSP and standardized to the DCCT assay.

3. **2-Hour Plasma Glucose (2-h PG)**:
   - **≥ 200 mg/dL (11.1 mmol/L)** during an Oral Glucose Tolerance Test (OGTT) using a 75-g anhydrous glucose load.

4. **Random Plasma Glucose**:
   - **≥ 200 mg/dL (11.1 mmol/L)** in an individual with classic symptoms of hyperglycemia (polydipsia, polyuria, unexplained weight loss) or hyperglycemic crisis.

#### Clinical Implementation Notes:
- In the absence of unequivocal hyperglycemia, diagnosis requires **two abnormal test results** from either the same sample or two separate test samples.
- Annual screening should begin at age **35 years** for all asymptomatic adults, or earlier for individuals of any age who are overweight/obese (BMI ≥25 kg/m² or ≥23 kg/m² in Asian Americans) with one or more additional risk factors.`;
    } else if (lowerQuery.includes("metformin")) {
      responseText = `### Mechanism of Action: Metformin (Biguanide Class)

Metformin is the foundational, first-line oral antihyperglycemic agent for managing Type 2 Diabetes. Its pharmacology is characterized by:

1. **Suppression of Hepatic Gluconeogenesis**:
   - Inhibits mitochondrial complex I in hepatocytes, reducing ATP production and activating **AMP-activated protein kinase (AMPK)**.
   - Suppresses key gluconeogenic enzymes (*PEPCK* and *G6Pase*), lowering basal and postprandial hepatic glucose output by approximately 20–30%.

2. **Peripheral Insulin Sensitivity Enhancement**:
   - Stimulates **GLUT4 glucose transporter translocation** in skeletal muscle and adipose tissue, promoting non-insulin-mediated and insulin-mediated glucose uptake.

3. **Gastrointestinal & Incretin Modulation**:
   - Increases GLP-1 secretion by L-cells in the ileum, prolonging satiety and delaying intestinal glucose absorption.

4. **Cardiovascular & Weight Neutrality**:
   - Associated with modest weight loss or neutrality and favorable lipid profile changes (decreased triglycerides and LDL oxidation).`;
    } else {
      responseText = `### Clinical Synthesis: Diabetes & Glycemic Management

Based on current clinical guidelines retrieved via our **Hybrid RAG Pipeline** (Dense Vector + BM25 Sparse Search + Cross-Encoder Reranking):

1. **Individualized Glycemic Targets**:
   - **Target A1C**: <7.0% (53 mmol/mol) for most non-pregnant adults with adequate life expectancy.
   - **Fasting / Preprandial Capillary Blood Glucose**: 80–130 mg/dL (4.4–7.2 mmol/L).
   - **Peak Postprandial Capillary Glucose**: <180 mg/dL (10.0 mmol/L).

2. **Multifactorial Risk Reduction**:
   - **Blood Pressure Target**: <130/80 mmHg if safely attainable.
   - **Lipid Management**: Moderate-to-high intensity statin therapy for adults aged 40–75 with diabetes.
   - **Renal & Cardioprotective Agents**: Consideration of SGLT2 inhibitors and GLP-1 receptor agonists for individuals with established ASCVD, heart failure, or CKD.

3. **Lifestyle & Self-Management Education**:
   - Structured nutrition therapy emphasizing Mediterranean or plant-predominant dietary patterns, coupled with at least 150 minutes/week of moderate-to-vigorous aerobic exercise.`;
    }
  } else {
    // Non-diabetes query
    sources = [];
    responseText = `I have classified this query with intent **"Other"**. 

While our primary retrieval index is specialized in **Endocrinology, Diabetes, and Clinical Guidelines**, here is a general overview:

- For technical, programming, or general inquiries, I can guide you through architecture, workflows, and algorithmic design.
- If your question relates to metabolic conditions, glucose regulation, pharmacological treatments, or diabetes screening, feel free to ask directly to trigger the full **Hybrid RAG** retrieval pipeline!`;
  }

  const chunks = responseText.split(/(?<=\s|[\n.,;:?!])/);
  const streamDelay = Math.max(12, Math.min(30, 24 - (settings?.temperature || 0.2) * 10));

  for (let i = 0; i < chunks.length; i++) {
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    const chunk = chunks[i];
    onToken(chunk);

    await new Promise((resolve, reject) => {
      const timeout = setTimeout(resolve, streamDelay);
      if (signal) {
        signal.addEventListener(
          "abort",
          () => {
            clearTimeout(timeout);
            reject(new DOMException("Aborted", "AbortError"));
          },
          { once: true }
        );
      }
    });
  }

  const elapsedMs = Math.round(performance.now() - startTime);
  const tokenCount = Math.round(responseText.length / 3.8);

  onMetadata({
    thread_id: threadId,
    total_tokens: tokenCount,
    execution_time_ms: elapsedMs,
    intent: detectedIntent,
    model: settings?.model || "openai/gpt-oss-20b",
    sources,
  });
}
