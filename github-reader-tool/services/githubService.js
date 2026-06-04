const fs = require("fs");
const path = require("path");

const TEXT_DOCUMENT_EXTENSIONS = [
  ".md",
  ".markdown",
  ".txt",
  ".rst",
  ".adoc",
  ".csv",
  ".tsv",
  ".rtf",
  ".tex"
];

const BINARY_DOCUMENT_EXTENSIONS = [
  ".pdf",
  ".doc",
  ".docx",
  ".odt",
  ".ppt",
  ".pptx",
  ".xls",
  ".xlsx"
];

const DOCUMENT_EXTENSIONS = [
  ...TEXT_DOCUMENT_EXTENSIONS,
  ...BINARY_DOCUMENT_EXTENSIONS
];

const STORAGE_ROOT = path.join(__dirname, "..", "storage", "repos");

function githubHeaders(githubToken) {
  const headers = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "github-reader-tool"
  };

  const token = githubToken || process.env.GITHUB_TOKEN;

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

async function readGithubError(response, fallbackMessage) {
  let message = fallbackMessage;

  try {
    const data = await response.json();
    if (data.message) {
      message = data.message;
    }
  } catch (_) {
    // Keep the fallback when GitHub does not return a JSON error body.
  }

  return `GitHub API error ${response.status}: ${message}`;
}

function parseGithubUrl(githubUrl) {
  const match = githubUrl.match(/github\.com\/([^\/]+)\/([^\/#?]+)/);

  if (!match) {
    throw new Error("Link GitHub khong hop le");
  }

  return {
    owner: match[1],
    repo: match[2].replace(".git", "")
  };
}

function getFileExtension(filePath) {
  const match = filePath.toLowerCase().match(/\.[^.]+$/);
  return match ? match[0] : "";
}

function isDocumentFile(filePath) {
  return DOCUMENT_EXTENSIONS.includes(getFileExtension(filePath));
}

function isTextDocument(filePath) {
  return TEXT_DOCUMENT_EXTENSIONS.includes(getFileExtension(filePath));
}

function buildRawUrl(owner, repo, filePath) {
  return `https://raw.githubusercontent.com/${owner}/${repo}/HEAD/${filePath}`;
}

function buildGithubFileUrl(owner, repo, filePath) {
  return `https://github.com/${owner}/${repo}/blob/HEAD/${filePath}`;
}

function sanitizePathPart(value) {
  return value.replace(/[<>:"\\|?*\x00-\x1F]/g, "_").replace(/^\.+$/, "_");
}

function safeRelativePath(filePath) {
  return filePath
    .split("/")
    .filter((part) => part && part !== "." && part !== "..")
    .map(sanitizePathPart)
    .join(path.sep);
}

function repoStorageDir(owner, repo) {
  return path.join(STORAGE_ROOT, `${sanitizePathPart(owner)}__${sanitizePathPart(repo)}`);
}

async function getRepoTree(owner, repo, githubToken) {
  const url = `https://api.github.com/repos/${owner}/${repo}/git/trees/HEAD?recursive=1`;

  const response = await fetch(url, {
    headers: githubHeaders(githubToken)
  });

  if (!response.ok) {
    throw new Error(await readGithubError(response, "Khong lay duoc danh sach file tu GitHub"));
  }

  const data = await response.json();
  return data.tree || [];
}

async function fetchDocument(owner, repo, filePath, githubToken) {
  const response = await fetch(buildRawUrl(owner, repo, filePath), {
    headers: githubHeaders(githubToken)
  });

  if (!response.ok) {
    return {
      content: "",
      buffer: Buffer.alloc(0)
    };
  }

  const arrayBuffer = await response.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);

  return {
    content: isTextDocument(filePath) ? buffer.toString("utf8") : "",
    buffer
  };
}

function saveRepoData({ owner, repo, githubUrl, files, knowledgeText }) {
  const savedDir = repoStorageDir(owner, repo);
  const documentsDir = path.join(savedDir, "documents");

  fs.mkdirSync(documentsDir, { recursive: true });

  const savedFiles = files.map((file) => {
    const relativePath = safeRelativePath(file.path);
    const localPath = path.join(documentsDir, relativePath);

    fs.mkdirSync(path.dirname(localPath), { recursive: true });
    fs.writeFileSync(localPath, file.buffer);

    return {
      path: file.path,
      size: file.size,
      extension: file.extension,
      type: file.type,
      rawUrl: file.rawUrl,
      htmlUrl: file.htmlUrl,
      localPath
    };
  });

  const metadata = {
    repo: `${owner}/${repo}`,
    githubUrl,
    savedAt: new Date().toISOString(),
    fileCount: savedFiles.length,
    allowedExtensions: DOCUMENT_EXTENSIONS,
    files: savedFiles
  };

  fs.writeFileSync(path.join(savedDir, "knowledge.txt"), knowledgeText, "utf8");
  fs.writeFileSync(path.join(savedDir, "metadata.json"), JSON.stringify(metadata, null, 2), "utf8");

  return {
    savedDir,
    knowledgePath: path.join(savedDir, "knowledge.txt"),
    metadataPath: path.join(savedDir, "metadata.json"),
    documentsDir,
    files: savedFiles
  };
}

async function readGithubRepo(githubUrl, githubToken) {
  const { owner, repo } = parseGithubUrl(githubUrl);
  const tree = await getRepoTree(owner, repo, githubToken);

  const documentFiles = tree
    .filter((item) => item.type === "blob")
    .filter((item) => isDocumentFile(item.path))
    .filter((item) => !item.path.includes("node_modules"))
    .filter((item) => item.size < 5000000);

  let knowledgeText = `REPO: ${owner}/${repo}\nSOURCE: ${githubUrl}\n`;
  const fileContents = [];
  const filesForStorage = [];

  for (const file of documentFiles) {
    const readableAsText = isTextDocument(file.path);
    const { content, buffer } = await fetchDocument(owner, repo, file.path, githubToken);

    knowledgeText += `\n\n--- FILE: ${file.path} ---\n`;
    knowledgeText += readableAsText
      ? content
      : `[Binary document file saved locally. Original: ${buildRawUrl(owner, repo, file.path)}]`;

    const fileInfo = {
      path: file.path,
      size: file.size,
      extension: getFileExtension(file.path),
      type: readableAsText ? "text" : "binary",
      rawUrl: buildRawUrl(owner, repo, file.path),
      htmlUrl: buildGithubFileUrl(owner, repo, file.path),
      content
    };

    fileContents.push(fileInfo);
    filesForStorage.push({
      ...fileInfo,
      buffer
    });
  }

  const saved = saveRepoData({
    owner,
    repo,
    githubUrl,
    files: filesForStorage,
    knowledgeText
  });

  return {
    repo: `${owner}/${repo}`,
    fileCount: documentFiles.length,
    files: fileContents.map((file) => {
      const savedFile = saved.files.find((item) => item.path === file.path);
      return {
        ...file,
        localPath: savedFile ? savedFile.localPath : null
      };
    }),
    text: knowledgeText,
    savedDir: saved.savedDir,
    knowledgePath: saved.knowledgePath,
    metadataPath: saved.metadataPath,
    documentsDir: saved.documentsDir,
    allowedExtensions: DOCUMENT_EXTENSIONS
  };
}

module.exports = {
  readGithubRepo
};
