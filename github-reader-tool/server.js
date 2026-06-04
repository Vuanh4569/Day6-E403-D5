const express = require("express");
const cors = require("cors");
const path = require("path");

const { readGithubRepo } = require("./services/githubService");

const app = express();

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

function detectScope(question) {
  const q = question.toLowerCase();

  if (
    q.includes("deadline") ||
    q.includes("nộp") ||
    q.includes("repo") ||
    q.includes("checkpoint") ||
    q.includes("demo")
  ) {
    return "Program Operations";
  }

  if (
    q.includes("spec") ||
    q.includes("build slice") ||
    q.includes("workflow") ||
    q.includes("path") ||
    q.includes("evidence")
  ) {
    return "Learning Content";
  }

  return "Ambiguous";
}

function normalizeForSearch(text) {
  return text
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/day\s*0*(\d+)/gi, "day$1");
}

function getKeywords(question) {
  return normalizeForSearch(question)
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, "")
    .split(/\s+/)
    .filter((word) => word.length >= 3)
    .filter((word) => !["làm", "gì", "như", "nào", "của", "cho", "với", "the", "and"].includes(word));
}

function splitIntoChunks(text) {
  return text
    .split(/--- FILE:/g)
    .filter(Boolean)
    .map((chunk) => "--- FILE:" + chunk.trim());
}

function scoreChunk(chunk, keywords) {
  const lower = normalizeForSearch(chunk).toLowerCase();
  let score = 0;

  for (const keyword of keywords) {
    if (lower.includes(keyword)) {
      score += 1;
    }
  }

  return score;
}

function findRelevantChunks(text, question) {
  const keywords = getKeywords(question);
  const chunks = splitIntoChunks(text);

  const scored = chunks
    .map((chunk) => ({
      chunk,
      score: scoreChunk(chunk, keywords)
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);

  return scored;
}

function cleanChunk(chunk) {
  return chunk
    .replace(/\n{3,}/g, "\n\n")
    .slice(0, 2500);
}

function buildAnswer({ question, repoResult }) {
  const scope = detectScope(question);
  const relevantChunks = findRelevantChunks(repoResult.text, question);

  if (relevantChunks.length === 0) {
    return {
      scope,
      sourceStatus: "Missing",
      answer: `
Detected scope: ${scope}

Source status: Missing

Mình chưa tìm thấy thông tin liên quan trong repo này.
Mình không đoán vì câu trả lời cần dựa trên source.

Draft hỏi mentor/TA:
"${question} — phần này nằm ở file nào trong repo hoặc source nào ạ?"
`
    };
  }

  const sources = relevantChunks
    .map((item) => {
      const firstLine = item.chunk.split("\n")[0];
      return firstLine.replace("--- FILE:", "").trim();
    })
    .join(", ");

  const evidenceText = relevantChunks
    .map((item, index) => {
      return `SOURCE ${index + 1}:\n${cleanChunk(item.chunk)}`;
    })
    .join("\n\n--------------------\n\n");

  const answer = `
Detected scope: ${scope}

Source status: Found

Matched source:
${sources}

Summary:
Mình tìm thấy thông tin liên quan trong repo. Dưới đây là phần nội dung phù hợp nhất từ các file đã đọc.

Relevant content:
${evidenceText}

Next step:
Dựa trên source trên, bạn hãy chọn đúng file cần làm hoặc hỏi tiếp cụ thể hơn, ví dụ:
- "Tóm tắt README.md"
- "Day05 cần nộp gì?"
- "Thin SPEC gồm những phần nào?"
`;

  return {
    scope,
    sourceStatus: "Found",
    answer
  };
}

app.post("/api/read-github", async (req, res) => {
  try {
    const { githubUrl, githubToken } = req.body;

    if (!githubUrl) {
      return res.status(400).json({
        success: false,
        error: "Thiếu githubUrl"
      });
    }

    const result = await readGithubRepo(githubUrl, githubToken);

    res.json({
      success: true,
      ...result
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

app.post("/api/ask", async (req, res) => {
  try {
    const { githubUrl, question, githubToken } = req.body;

    if (!githubUrl || !question) {
      return res.status(400).json({
        success: false,
        error: "Thiếu githubUrl hoặc question"
      });
    }

    const repoResult = await readGithubRepo(githubUrl, githubToken);

    const result = buildAnswer({
      question,
      repoResult
    });

    res.json({
      success: true,
      repo: repoResult.repo,
      fileCount: repoResult.fileCount,
      question,
      scope: result.scope,
      sourceStatus: result.sourceStatus,
      answer: result.answer
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

app.listen(3000, () => {
  console.log("Server running on http://localhost:3000");
});
