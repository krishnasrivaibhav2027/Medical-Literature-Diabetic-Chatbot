/**
 * Dynamically and randomly generates greetings for the empty chat screen
 * Incorporates time-of-day awareness and welcome variations per user requirements.
 */

export function generateDynamicGreeting(firstName = "Andrew") {
  const now = new Date();
  const hour = now.getHours();

  // Time-aware greeting options
  let timeOptions = [];
  if (hour >= 5 && hour < 12) {
    timeOptions = [
      `Good morning, ${firstName}! How can I help you today?`,
      `Good morning, ${firstName}! Ready to explore medical insights and research?`,
      `Good morning, ${firstName}! What would you like to analyze today?`,
    ];
  } else if (hour >= 12 && hour < 17) {
    timeOptions = [
      `Good afternoon, ${firstName}! What brings you here today?`,
      `Good afternoon, ${firstName}! How can I assist your workflow today?`,
      `Good afternoon, ${firstName}! What's on your mind?`,
    ];
  } else if (hour >= 17 && hour < 22) {
    timeOptions = [
      `Good evening, ${firstName}! What would you like to discuss tonight?`,
      `Good evening, ${firstName}! How can I help you with your questions?`,
      `Good evening, ${firstName}! Ready to dive into medical guidelines?`,
    ];
  } else {
    timeOptions = [
      `Welcome, ${firstName}! Working late? I'm here to assist you.`,
      `Good night, ${firstName}! What can I help you look up?`,
      `Late night research, ${firstName}? Let's find what you need.`,
    ];
  }

  // Welcome & general greeting variations
  const welcomeOptions = [
    `Welcome, ${firstName}, what brings you here?`,
    `Welcome, ${firstName}! What would you like to explore today?`,
    `Hello, ${firstName}! Ask me anything about diabetes research or clinical guidelines.`,
    `Welcome back, ${firstName}! How can I make your day easier?`,
    `Hi ${firstName}! Ready to explore the Hybrid RAG knowledge base?`,
  ];

  // Randomly select either time-based or general welcome
  const useTimeBased = Math.random() > 0.5;
  const pool = useTimeBased ? timeOptions : welcomeOptions;
  const selectedGreeting = pool[Math.floor(Math.random() * pool.length)];

  const subtitles = [
    "Powered by Hybrid RAG (Dense Vector + BM25 Sparse Search + Cross-Encoder Reranking)",
    "Ask clinical questions, explore diabetes guidelines, or get structured research summaries",
    "Tailored medical insights backed by verified knowledge bases and real-time retrieval",
    "Enter a prompt below or pick one of the recommended starter queries to begin",
  ];

  const selectedSubtitle = subtitles[Math.floor(Math.random() * subtitles.length)];

  return {
    greeting: selectedGreeting,
    subtitle: selectedSubtitle,
    timestamp: now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  };
}

export const SUGGESTED_PROMPTS = [
  {
    title: "Type 2 Diabetes Screening",
    prompt: "What are the recommended screening guidelines and criteria for diagnosing Type 2 Diabetes according to ADA 2024?",
    tag: "Clinical Criteria",
  },
  {
    title: "Metformin Mechanism & Action",
    prompt: "Explain how Metformin reduces hepatic gluconeogenesis and its effects on insulin sensitivity.",
    tag: "Pharmacology",
  },
  {
    title: "Diabetic Ketoacidosis (DKA)",
    prompt: "What are the early warning signs, laboratory thresholds, and emergency interventions for Diabetic Ketoacidosis?",
    tag: "Emergency Protocols",
  },
  {
    title: "Continuous Glucose Monitoring (CGM)",
    prompt: "How does Continuous Glucose Monitoring improve Time in Range (TIR) for diabetic management?",
    tag: "Technology & Care",
  },
];
