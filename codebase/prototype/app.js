const routePill = document.querySelector("#routePill");
const chatWindow = document.querySelector("#chatWindow");
const questionInput = document.querySelector("#questionInput");
const sourceInput = document.querySelector("#sourceInput");
const sendBtn = document.querySelector("#sendBtn");
const resetBtn = document.querySelector("#resetBtn");
const loadSourceBtn = document.querySelector("#loadSourceBtn");
const sampleTextBtn = document.querySelector("#sampleTextBtn");
const sampleGitBtn = document.querySelector("#sampleGitBtn");
const samplePdfBtn = document.querySelector("#samplePdfBtn");
const sampleGeneralBtn = document.querySelector("#sampleGeneralBtn");
const sampleCourseBtn = document.querySelector("#sampleCourseBtn");
const sampleAmbiguousBtn = document.querySelector("#sampleAmbiguousBtn");
const sampleOpsBtn = document.querySelector("#sampleOpsBtn");
const traceList = document.querySelector("#traceList");
const toolList = document.querySelector("#toolList");
const sourceList = document.querySelector("#sourceList");
const evidenceList = document.querySelector("#evidenceList");
const answerContract = document.querySelector("#answerContract");
const refusalBox = document.querySelector("#refusalBox");

const adapters = {
  async tavilySearch(query) {
    if (canUseBackend()) {
      const response = await apiPost("/api/tools/tavily", { query });
      return response.evidence || [];
    }
    if (window.learningAgentAdapters?.tavilySearch) {
      return window.learningAgentAdapters.tavilySearch(query);
    }
    return mockTavilySearch(query);
  },
  async readGitHub(url) {
    if (window.learningAgentAdapters?.readGitHub) {
      return window.learningAgentAdapters.readGitHub(url);
    }
    return {
      status: "adapter_missing",
      title: "GitHub reader chưa được cắm",
      text:
        "GitHub source detected. Tool GitHub reader cần list README/docs/rubric/notebook markdown, sau đó trả text chunks cho agent.",
      note: "Stub đang chờ tool của teammate."
    };
  },
  async readPdf(url) {
    if (window.learningAgentAdapters?.readPdf) {
      return window.learningAgentAdapters.readPdf(url);
    }
    return {
      status: "adapter_missing",
      title: "PDF reader chưa được cắm",
      text:
        "PDF source detected. Tool PDF reader cần extract text theo page, chunk theo section, và báo OCR-needed nếu PDF là scan.",
      note: "Stub đang chờ tool của teammate."
    };
  }
};

function canUseBackend() {
  return window.location.protocol === "http:" || window.location.protocol === "https:";
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`API ${path} failed: ${response.status}`);
  }
  return response.json();
}

const samples = {
  text:
    "Day05 thin SPEC: Evidence là nhóm thấy pain thật ở đâu, nguồn nào, quote/screenshot nào. Build slice là một user, một task, một AI decision, một output. 4 paths gồm happy, low-confidence, failure, correction. Day05 không cần PRD đầy đủ, chỉ cần SPEC đủ để build.",
  github: "https://github.com/VinUni-AI20k/Batch02-Day05-AI-Product-Labs",
  pdf: "https://example.com/ai-in-action-day05-slides.pdf",
  general: "Build slice là gì trong product management?",
  course: "Trong slide Day05, build slice là gì?",
  ambiguous: "Bài này làm sao?",
  ops: "Deadline nộp repo là mấy giờ?"
};

const state = {
  messages: [],
  sources: [],
  memory: {
    lastRoute: "ready",
    missingInfo: [],
    corrections: []
  },
  lastRun: {
    trace: [],
    tools: [],
    evidence: [],
    contract: "",
    refusal: ""
  }
};

function hasAny(text, words) {
  return words.some((word) => text.includes(word));
}

function normalizeText(text) {
  return text.toLowerCase().normalize("NFC");
}

function detectSourceType(raw) {
  const text = raw.trim().toLowerCase();
  if (!text) return "empty";
  if (text.includes("github.com") && !text.includes("/blob/") && !text.includes("/raw/")) return "github_repo";
  if (text.includes("github.com") && text.includes("/blob/")) return "github_file";
  if (text.endsWith(".pdf") || text.includes(".pdf?")) return "pdf";
  if (text.startsWith("http://") || text.startsWith("https://")) return "web";
  return "pasted_text";
}

function detectRoute(question) {
  const text = normalizeText(question);

  if (hasAny(text, ["deadline", "hạn nộp", "nộp repo", "repo cá nhân", "repo nhóm", "grading", "điểm", "lịch", "mấy giờ"])) {
    return "ops";
  }

  if (hasAny(text, ["bài này", "cái này", "làm sao", "không hiểu", "nó là gì"]) && !hasAny(text, ["slide", "day05", "day06", "lab", "rubric"])) {
    return "ambiguous";
  }

  if (hasAny(text, ["trong slide", "theo slide", "day05", "day06", "lab", "rubric", "bài lab", "khóa học", "ai thực chiến", "thầy nói", "mentor nói", "repo bài"])) {
    return "course";
  }

  return "general";
}

function sourceIsCourse(source) {
  return ["pasted_text", "github_repo", "github_file", "pdf", "web"].includes(source.type);
}

function chunkText(text, meta) {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return [];
  const chunks = [];
  for (let index = 0; index < cleaned.length; index += 520) {
    chunks.push({
      id: `${meta.id}-chunk-${chunks.length + 1}`,
      text: cleaned.slice(index, index + 520),
      meta: { ...meta, chunk_id: chunks.length + 1 }
    });
  }
  return chunks;
}

function keywordsFor(question) {
  const text = normalizeText(question);
  const groups = [
    ["build slice", "slice", "lát cắt"],
    ["thin spec", "spec"],
    ["failure path", "failure"],
    ["happy path", "happy"],
    ["low-confidence", "low confidence", "không chắc"],
    ["evidence", "evidence pack"],
    ["rag", "retrieval"],
    ["agentic", "workflow", "agent"],
    ["rubric", "checklist"]
  ];
  const matched = groups.flatMap((group) => group.filter((word) => text.includes(word)));
  if (matched.length) return matched;
  return text.split(/\s+/).filter((word) => word.length > 3).slice(0, 8);
}

function retrieveFromSources(question) {
  const keywords = keywordsFor(question);
  const chunks = state.sources.flatMap((source) => source.chunks);

  return chunks
    .map((chunk) => {
      const body = normalizeText(chunk.text);
      const score = keywords.reduce((total, keyword) => total + (body.includes(keyword) ? 1 : 0), 0);
      return { ...chunk, score };
    })
    .filter((chunk) => chunk.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 4);
}

function renderList(container, items) {
  container.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    container.appendChild(li);
  });
}

function pushMessage(role, text, actions = []) {
  state.messages.push({ role, text, actions });
  renderChat();
}

function renderChat() {
  chatWindow.innerHTML = "";
  state.messages.forEach((message) => {
    const bubble = document.createElement("article");
    bubble.className = `message ${message.role}`;
    const body = document.createElement("div");
    body.className = "message-body";
    body.textContent = message.text;
    bubble.appendChild(body);

    if (message.actions?.length) {
      const actionWrap = document.createElement("div");
      actionWrap.className = "message-actions";
      message.actions.forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "option";
        button.textContent = action.label;
        button.addEventListener("click", () => action.handler());
        actionWrap.appendChild(button);
      });
      bubble.appendChild(actionWrap);
    }

    chatWindow.appendChild(bubble);
  });
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function renderState() {
  routePill.textContent = routeLabel(state.memory.lastRoute);
  routePill.className = `status-pill ${state.memory.lastRoute === "general" || state.memory.lastRoute === "course" ? "ok" : state.memory.lastRoute === "ready" ? "" : "low"}`;

  renderList(traceList, state.lastRun.trace.length ? state.lastRun.trace : ["Agent chưa chạy."]);
  renderList(toolList, state.lastRun.tools.length ? state.lastRun.tools : ["Chưa gọi tool."]);
  renderList(
    sourceList,
    state.sources.length
      ? state.sources.map((source) => `${source.title} · ${source.type} · ${source.status} · ${source.chunks.length} chunk(s)`)
      : ["Chưa có course source. Nếu user hỏi nội dung khóa học, agent sẽ xin link/tài liệu."]
  );
  renderList(
    evidenceList,
    state.lastRun.evidence.length
      ? state.lastRun.evidence.map(formatEvidenceItem)
      : ["Chưa có retrieved evidence."]
  );
  answerContract.textContent = state.lastRun.contract || "Agent chưa chạy.";
  answerContract.classList.toggle("muted", !state.lastRun.contract);
  refusalBox.textContent = state.lastRun.refusal || "Không có refusal ở lượt này.";
  refusalBox.classList.toggle("muted", !state.lastRun.refusal);
}

function formatEvidenceItem(item) {
  if (item.meta) {
    return `${item.meta.title} · chunk ${item.meta.chunk_id}: ${item.text}`;
  }
  if (item.title || item.url || item.snippet) {
    return `${item.title || "Source"} · ${item.url || "no-url"}: ${item.snippet || item.text || ""}`;
  }
  return `${item.title || "Chunk"} · chunk ${item.chunk_id || "?"}: ${item.text || JSON.stringify(item)}`;
}

function routeLabel(route) {
  return {
    ready: "Ready",
    course: "Course-grounded",
    general: "General",
    ambiguous: "Needs context",
    ops: "Refusal"
  }[route] || route;
}

function sourceStatusForCourse() {
  if (!state.sources.length) return "Missing course source";
  return "Course source loaded";
}

function askForCourseSource(question) {
  const trace = [
    "Read question and conversation memory.",
    "Route = Course-grounded.",
    "Course source is missing.",
    "Ask user to provide GitHub/PDF/link/text before answering."
  ];
  const tools = ["No Git/PDF tool call because no source was provided."];
  const message = [
    "Mình cần tài liệu liên quan của khóa học trước khi trả lời câu này.",
    "Bạn paste GitHub repo/file link, PDF/slide link, hoặc đoạn text từ README/rubric được không?",
    "",
    `Câu hỏi đang giữ trong memory: "${question}"`
  ].join("\n");

  state.lastRun = {
    trace,
    tools,
    evidence: [],
    contract: [
      "Detected route: Course-grounded",
      "Source status: Missing course source",
      "Answer: Chưa trả lời để tránh đoán sai nội dung khóa học.",
      "Next action: User paste source rồi agent ingest/retrieve trong cùng conversation."
    ].join("\n"),
    refusal: "Không đoán nội dung slide/lab/rubric khi chưa có source khóa học."
  };

  pushMessage("agent", message, [
    {
      label: "Load sample source",
      handler: () => {
        sourceInput.value = samples.text;
        loadSource();
      }
    },
    {
      label: "Use GitHub sample",
      handler: () => {
        sourceInput.value = samples.github;
        loadSource();
      }
    },
    {
      label: "Use PDF sample",
      handler: () => {
        sourceInput.value = samples.pdf;
        loadSource();
      }
    }
  ]);
}

function buildCourseAnswer(question, evidence) {
  const text = normalizeText(question);
  const cited = evidence.map((item) => `${item.meta.title} chunk ${item.meta.chunk_id}`).join("; ");

  let summary = "Mình tìm thấy nội dung liên quan trong source khóa học và tổng hợp theo tài liệu đã load.";
  if (hasAny(text, ["build slice", "slice"])) {
    summary = "Build slice là lát cắt nhỏ đủ để demo: một user, một task, một AI decision và một output nhìn thấy được.";
  } else if (hasAny(text, ["thin spec", "spec"])) {
    summary = "Thin SPEC là bản mô tả đủ để build prototype, tập trung evidence, slice, decision, failure path và owner plan.";
  } else if (hasAny(text, ["failure"])) {
    summary = "Failure path là tình huống AI/product sai, thiếu nguồn hoặc không đủ tự tin; prototype phải thể hiện cách recover.";
  }

  return {
    message: [
      summary,
      "",
      "Cách áp dụng:",
      "1. Chọn đúng khái niệm/lab đang hỏi.",
      "2. Đối chiếu với source đã load.",
      "3. Viết output thành checklist hoặc decision ngắn.",
      "4. Nếu source thiếu hoặc mâu thuẫn, hỏi mentor thay vì tự đoán.",
      "",
      `Evidence: ${cited}`
    ].join("\n"),
    checklist: [
      "Detected route: Course-grounded",
      "Source status: Found in loaded course source",
      `Reasoning summary: retrieved ${evidence.length} chunk(s), then summarized only from loaded course source.`,
      `Answer summary: ${summary}`,
      "Next action: áp dụng vào thin-spec/workflow hoặc hỏi mentor nếu cần source mới."
    ].join("\n")
  };
}

async function buildGeneralAnswer(question) {
  const results = await adapters.tavilySearch(question);
  const sources = results.map((item, index) => `${index + 1}. ${item.title} (${item.url})`).join("\n");
  const answer = synthesizeGeneral(question, results);
  return {
    answer,
    evidence: results.map((item, index) => ({
      id: `web-${index + 1}`,
      text: item.snippet,
      meta: {
        title: item.title,
        chunk_id: index + 1,
        source_url: item.url,
        source_type: "tavily_result"
      }
    })),
    contract: [
      "Detected route: General learning",
      "Source status: Public source found via Tavily",
      `Reasoning summary: searched public web, compared ${results.length} result(s), then answered as general knowledge.`,
      `Answer summary: ${answer.split("\n")[0]}`,
      "Sources:",
      sources
    ].join("\n")
  };
}

function synthesizeGeneral(question, results) {
  const text = normalizeText(question);
  if (hasAny(text, ["build slice", "slice"])) {
    return [
      "Build slice là một phần rất nhỏ của sản phẩm được chọn để chứng minh giá trị hoặc rủi ro chính.",
      "Reasoning: các nguồn về product discovery/MVP đều nhấn mạnh việc giảm scope để học nhanh. Với AI product, slice nên có một user, một task, một AI decision và một output kiểm chứng được.",
      "Gợi ý áp dụng vào bài: đừng build cả Learning OS; chỉ demo một câu hỏi học tập đi qua route, search/source check, answer/refusal."
    ].join("\n");
  }
  if (hasAny(text, ["rag", "retrieval"])) {
    return [
      "RAG là cách cho mô hình tìm tài liệu liên quan trước, rồi dùng tài liệu đó để trả lời.",
      "Reasoning: workflow này giảm rủi ro bịa vì câu trả lời được neo vào retrieved evidence.",
      "Gợi ý áp dụng vào bài: Tavily/Git/PDF reader là phần retrieval, Answer Composer là phần tổng hợp."
    ].join("\n");
  }
  return [
    "Đây là câu hỏi kiến thức chung nên agent dùng Tavily search trước khi trả lời.",
    "Reasoning: không có dấu hiệu cần bám slide/lab cụ thể, nên có thể tổng hợp từ public sources.",
    `Tóm tắt: ${results[0]?.snippet || "Không có snippet đủ rõ."}`
  ].join("\n");
}

function askClarifyingQuestion(question) {
  state.lastRun = {
    trace: [
      "Read question and conversation memory.",
      "Route = Ambiguous.",
      "Ask one short clarification before tool call."
    ],
    tools: ["No tool call yet."],
    evidence: [],
    contract: [
      "Detected route: Ambiguous",
      "Source status: Waiting for clarification",
      "Next action: user selects topic/source/goal; agent keeps same conversation."
    ].join("\n"),
    refusal: ""
  };

  pushMessage("agent", "Bạn đang hỏi theo hướng nào để mình xử lý đúng?", [
    {
      label: "Kiến thức chung",
      handler: () => runAgent(`${question} trong kiến thức chung`)
    },
    {
      label: "Theo tài liệu khóa học",
      handler: () => runAgent(`${question} theo slide/lab khóa học`)
    },
    {
      label: "Checklist áp dụng",
      handler: () => runAgent(`${question}. Tôi muốn checklist áp dụng vào bài lab.`)
    }
  ]);
}

function refuseOps(question) {
  const draft = `Mentor/TA ơi, thông tin chính thức mới nhất về "${question}" là gì, và nguồn nào nên dùng để kiểm chứng?`;
  state.lastRun = {
    trace: [
      "Read question and conversation memory.",
      "Route = Program Operations.",
      "No official source loaded.",
      "Refuse to guess internal rule/deadline."
    ],
    tools: ["No Tavily/Git/PDF call because ops rule needs official source."],
    evidence: [],
    contract: [
      "Detected route: Program Operations",
      "Source status: Missing official source",
      "Answer summary: Không trả lời chắc về deadline/rule nội bộ.",
      `Suggested follow-up: ${draft}`
    ].join("\n"),
    refusal: "Không đoán deadline, rule nộp repo, grading hoặc lịch nếu chưa có source chính thức."
  };

  pushMessage("agent", [
    "Mình không nên đoán rule/deadline nội bộ.",
    "Bạn paste source chính thức nếu có, còn không thì có thể hỏi mentor bằng câu này:",
    `"${draft}"`
  ].join("\n"));
}

async function runAgent(rawQuestion) {
  const question = rawQuestion.trim();
  if (!question) return;

  pushMessage("user", question);
  questionInput.value = "";

  if (canUseBackend()) {
    try {
      const result = await apiPost("/api/ask", { question });
      state.memory.lastRoute = normalizeBackendRoute(result.route);
      state.lastRun = {
        trace: result.trace || [],
        tools: result.tool_calls || [],
        evidence: result.evidence || [],
        contract: [
          `Detected route: ${result.route}`,
          `Source status: ${result.source_status}`,
          "",
          result.answer || "",
          result.suggested_follow_up ? `\nSuggested follow-up: ${result.suggested_follow_up}` : ""
        ].join("\n"),
        refusal: result.refusal || ""
      };
      pushMessage("agent", result.answer || "Agent không có câu trả lời.");
      renderState();
      return;
    } catch (error) {
      pushMessage("agent", `Backend API lỗi, fallback sang demo local.\n${error.message}`);
    }
  }

  const route = detectRoute(question);
  state.memory.lastRoute = route;

  if (route === "ambiguous") {
    askClarifyingQuestion(question);
    renderState();
    return;
  }

  if (route === "ops") {
    refuseOps(question);
    renderState();
    return;
  }

  if (route === "course") {
    if (!state.sources.some(sourceIsCourse)) {
      askForCourseSource(question);
      renderState();
      return;
    }

    const trace = [
      "Read question and conversation memory.",
      "Route = Course-grounded.",
      "Course source exists.",
      "Retrieve relevant chunks from loaded source.",
      "Compose answer only from source evidence."
    ];
    const tools = ["Course Source Retriever: local chunks from pasted/Git/PDF/web source."];
    const evidence = retrieveFromSources(question);

    if (!evidence.length) {
      state.lastRun = {
        trace: [...trace, "Source check = Missing relevant chunk."],
        tools,
        evidence: [],
        contract: [
          "Detected route: Course-grounded",
          "Source status: Course source loaded, but no relevant chunk found",
          "Answer summary: Không trả lời chắc vì source không có đoạn liên quan.",
          "Next action: paste đúng slide/repo/PDF hoặc hỏi mentor."
        ].join("\n"),
        refusal: "Không tìm thấy đoạn liên quan trong source đã load, nên agent không đoán."
      };
      pushMessage("agent", "Mình có source khóa học, nhưng chưa tìm thấy đoạn liên quan đến câu hỏi này. Bạn paste thêm đúng slide/repo/PDF hoặc đoạn text liên quan nhé.");
      renderState();
      return;
    }

    const answer = buildCourseAnswer(question, evidence);
    state.lastRun = {
      trace,
      tools,
      evidence,
      contract: answer.checklist,
      refusal: ""
    };
    pushMessage("agent", answer.message);
    renderState();
    return;
  }

  const trace = [
    "Read question and conversation memory.",
    "Route = General learning.",
    "Use Tavily public search.",
    "Synthesize reasoning from public results.",
    "Return answer with source URLs."
  ];
  const tools = [`Tavily Search: "${question}"`];
  const answer = await buildGeneralAnswer(question);
  state.lastRun = {
    trace,
    tools,
    evidence: answer.evidence,
    contract: answer.contract,
    refusal: ""
  };
  pushMessage("agent", answer.answer);
  renderState();
}

function normalizeBackendRoute(route) {
  return {
    course_grounded: "course",
    general_learning: "general",
    program_operations: "ops",
    ambiguous: "ambiguous"
  }[route] || route || "ready";
}

async function loadSource() {
  const raw = sourceInput.value.trim();
  const type = detectSourceType(raw);
  if (type === "empty") return;

  if (canUseBackend()) {
    try {
      const result = await apiPost("/api/source", { source: raw });
      const source = {
        id: `source-${state.sources.length + 1}`,
        type: result.type || type,
        title: result.title || "Backend source",
        status: result.status || "Loaded",
        url: raw,
        note: result.note || "",
        chunks: []
      };
      state.sources.push(source);
      sourceInput.value = "";
      state.lastRun = {
        trace: ["Backend source ingestion.", `Detected source type = ${source.type}.`, `Chunks = ${result.chunks || 0}.`],
        tools: [`/api/source: ${source.type}`],
        evidence: [],
        contract: [
          "Detected route: Source ingestion",
          `Source status: ${source.status}`,
          `Loaded source: ${source.title}`,
          `Chunks: ${result.chunks || 0}`,
          `Note: ${source.note}`
        ].join("\n"),
        refusal: source.status === "missing" || source.status === "ocr_needed" ? source.note : ""
      };
      pushMessage("agent", `Backend đã load source: ${source.title}. Bây giờ bạn có thể hỏi câu bám theo tài liệu khóa học.`);
      renderState();
      return;
    } catch (error) {
      pushMessage("agent", `Backend source API lỗi, fallback sang loader local.\n${error.message}`);
    }
  }

  const id = `source-${state.sources.length + 1}`;
  const retrievedAt = new Date().toLocaleString("vi-VN");
  let source;

  if (type === "github_repo" || type === "github_file") {
    const result = await adapters.readGitHub(raw);
    source = {
      id,
      type,
      title: result.title || "GitHub source",
      status: result.status === "adapter_missing" ? "Adapter pending" : "Loaded",
      url: raw,
      note: result.note || "GitHub content loaded.",
      chunks: chunkText(result.text || "", { id, type, title: result.title || "GitHub source", source_url: raw, retrieved_at: retrievedAt })
    };
    state.lastRun.tools = [`GitHub Reader: ${raw}`];
  } else if (type === "pdf") {
    const result = await adapters.readPdf(raw);
    source = {
      id,
      type,
      title: result.title || "PDF source",
      status: result.status === "adapter_missing" ? "Adapter pending" : "Loaded",
      url: raw,
      note: result.note || "PDF content loaded.",
      chunks: chunkText(result.text || "", { id, type, title: result.title || "PDF source", source_url: raw, retrieved_at: retrievedAt })
    };
    state.lastRun.tools = [`PDF Reader: ${raw}`];
  } else if (type === "web") {
    source = {
      id,
      type,
      title: "Web source link",
      status: "Loaded as link",
      url: raw,
      note: "Tavily có thể search/read web link này ở bản backend.",
      chunks: chunkText(`Web source link provided: ${raw}. Use Tavily reader/search to fetch readable content before answering course-grounded questions.`, {
        id,
        type,
        title: "Web source link",
        source_url: raw,
        retrieved_at: retrievedAt
      })
    };
    state.lastRun.tools = [`Web Source Placeholder: ${raw}`];
  } else {
    source = {
      id,
      type,
      title: "Pasted course text",
      status: "Loaded",
      url: "pasted-text",
      note: "Text đã sẵn sàng để retrieve.",
      chunks: chunkText(raw, { id, type, title: "Pasted course text", source_url: "pasted-text", retrieved_at: retrievedAt })
    };
    state.lastRun.tools = ["Pasted Text Loader"];
  }

  state.sources.push(source);
  sourceInput.value = "";
  state.lastRun.trace = ["Load source.", `Detected source type = ${type}.`, `Created ${source.chunks.length} chunk(s).`];
  state.lastRun.evidence = [];
  state.lastRun.contract = [
    "Detected route: Source ingestion",
    `Source status: ${source.status}`,
    `Loaded source: ${source.title}`,
    `Chunks: ${source.chunks.length}`,
    `Note: ${source.note}`
  ].join("\n");
  state.lastRun.refusal = source.status === "Adapter pending" ? "Tool adapter đang chờ teammate cắm implementation thật." : "";
  pushMessage("agent", `Đã load source: ${source.title}. Bây giờ bạn có thể hỏi câu bám theo tài liệu khóa học.`);
  renderState();
}

function mockTavilySearch(query) {
  const text = normalizeText(query);
  if (hasAny(text, ["build slice", "slice"])) {
    return [
      {
        title: "MVP and product slice concept",
        url: "https://www.productplan.com/glossary/minimum-viable-product/",
        snippet: "MVP/product slice focuses on the smallest useful product version that can create learning from real users."
      },
      {
        title: "Agile vertical slicing",
        url: "https://www.agilealliance.org/glossary/vertical-slicing/",
        snippet: "Vertical slicing breaks work into small end-to-end increments that deliver visible user value."
      }
    ];
  }
  if (hasAny(text, ["rag", "retrieval"])) {
    return [
      {
        title: "Retrieval-augmented generation overview",
        url: "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
        snippet: "Retrieval-augmented generation retrieves relevant documents before generating an answer."
      },
      {
        title: "RAG pattern",
        url: "https://www.promptingguide.ai/techniques/rag",
        snippet: "RAG grounds model outputs in external context to improve factuality and source alignment."
      }
    ];
  }
  return [
    {
      title: "Public web result",
      url: "https://example.com/search-result",
      snippet: `Mock Tavily result for: ${query}. Backend can replace this with real Tavily API output.`
    }
  ];
}

function resetApp() {
  state.messages = [];
  state.sources = [];
  state.memory = { lastRoute: "ready", missingInfo: [], corrections: [] };
  state.lastRun = { trace: [], tools: [], evidence: [], contract: "", refusal: "" };
  questionInput.value = "";
  sourceInput.value = "";
  pushMessage("agent", "Chào Phúc, mình là Learning OS Support Agent. Hỏi kiến thức chung thì mình search web; hỏi bài học/slide/lab cụ thể thì mình sẽ xin source khóa học trước.");
  renderState();
}

sendBtn.addEventListener("click", () => runAgent(questionInput.value));
questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    runAgent(questionInput.value);
  }
});
resetBtn.addEventListener("click", resetApp);
loadSourceBtn.addEventListener("click", loadSource);
sampleTextBtn.addEventListener("click", () => {
  sourceInput.value = samples.text;
});
sampleGitBtn.addEventListener("click", () => {
  sourceInput.value = samples.github;
});
samplePdfBtn.addEventListener("click", () => {
  sourceInput.value = samples.pdf;
});
sampleGeneralBtn.addEventListener("click", () => {
  questionInput.value = samples.general;
});
sampleCourseBtn.addEventListener("click", () => {
  questionInput.value = samples.course;
});
sampleAmbiguousBtn.addEventListener("click", () => {
  questionInput.value = samples.ambiguous;
});
sampleOpsBtn.addEventListener("click", () => {
  questionInput.value = samples.ops;
});

resetApp();
