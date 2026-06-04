const STORAGE_KEY = "learning_os_agent_chats";
const ACTIVE_KEY = "learning_os_agent_active_chat";
const THEME_KEY = "learning_os_agent_theme";

const chatCard = document.querySelector(".chat-card");
const form = document.querySelector("#chatForm");
const input = document.querySelector("#chatInput");
const messages = document.querySelector("#messages");
const attachButton = document.querySelector("#attachButton");
const fileInput = document.querySelector("#fileInput");
const fileList = document.querySelector("#fileList");
const menuButton = document.querySelector("#menuButton");
const closeDrawer = document.querySelector("#closeDrawer");
const drawerBackdrop = document.querySelector("#drawerBackdrop");
const newChatButton = document.querySelector("#newChatButton");
const headerNewChatButton = document.querySelector("#headerNewChatButton");
const historyList = document.querySelector("#historyList");
const quickPrompts = document.querySelector("#quickPrompts");
const themeToggle = document.querySelector("#themeToggle");

let memoryStore = {};
let selectedFiles = [];

function canUseBackend() {
  return window.location.protocol === "http:" || window.location.protocol === "https:";
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`API ${path} failed: ${response.status}`);
  }
  return response.json();
}

// Helper functions for state
function storageGet(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    return memoryStore[key] || null;
  }
}

function storageSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    memoryStore[key] = value;
  }
}

function createId() {
  return "chat-" + Date.now() + "-" + Math.random().toString(16).slice(2);
}

function createConversation(title) {
  return {
    id: createId(),
    title: title || "Đoạn chat mới",
    createdAt: new Date().toISOString(),
    messages: [],
  };
}

function normalizeConversation(chat) {
  return {
    id: chat && chat.id ? String(chat.id) : createId(),
    title: chat && chat.title ? String(chat.title) : "Đoạn chat mới",
    createdAt: chat && chat.createdAt ? chat.createdAt : new Date().toISOString(),
    messages: Array.isArray(chat && chat.messages) ? chat.messages : [],
  };
}

function loadConversations() {
  try {
    const saved = JSON.parse(storageGet(STORAGE_KEY) || "[]");
    if (Array.isArray(saved) && saved.length) {
      return saved.map(normalizeConversation);
    }
  } catch (error) {
    return [createConversation()];
  }
  return [createConversation()];
}

let conversations = loadConversations();
let activeId = storageGet(ACTIVE_KEY);

if (!activeId || !conversations.some((chat) => chat.id === activeId)) {
  activeId = conversations[0].id;
}

function saveState() {
  storageSet(STORAGE_KEY, JSON.stringify(conversations));
  storageSet(ACTIVE_KEY, activeId);
}

function getActiveConversation() {
  return conversations.find((chat) => chat.id === activeId) || conversations[0];
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatDate(value) {
  try {
    return new Intl.DateTimeFormat("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch (error) {
    return "Gần đây";
  }
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

function setDrawer(open) {
  chatCard.classList.toggle("drawer-open", open);
}

/* ==========================================================================
   THEME MANAGEMENT
   ========================================================================== */
function initTheme() {
  const savedTheme = storageGet(THEME_KEY);
  const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  
  if (savedTheme === "dark" || (!savedTheme && systemPrefersDark)) {
    document.body.classList.add("dark-theme");
  } else {
    document.body.classList.remove("dark-theme");
  }
}

themeToggle.addEventListener("click", () => {
  document.body.classList.toggle("dark-theme");
  const isDark = document.body.classList.contains("dark-theme");
  storageSet(THEME_KEY, isDark ? "dark" : "light");
});

/* ==========================================================================
   MARKDOWN PARSER
   ========================================================================== */
function parseMarkdown(text) {
  const blocks = [];
  const codeBlockRegex = /```(\w*)\n([\s\S]*?)\n?```/g;
  let lastIndex = 0;
  let match;
  
  while ((match = codeBlockRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({
        type: 'text',
        content: text.slice(lastIndex, match.index)
      });
    }
    blocks.push({
      type: 'code',
      lang: match[1] || 'code',
      content: match[2]
    });
    lastIndex = codeBlockRegex.lastIndex;
  }
  
  if (lastIndex < text.length) {
    blocks.push({
      type: 'text',
      content: text.slice(lastIndex)
    });
  }
  
  if (blocks.length === 0) {
    blocks.push({ type: 'text', content: text });
  }
  
  return blocks.map(block => {
    if (block.type === 'code') {
      const escapedCode = escapeHtml(block.content);
      const language = block.lang || 'code';
      return `<div class="code-block-container">
        <div class="code-header">
          <span class="code-lang">${escapeHtml(language)}</span>
          <button class="code-copy-btn" type="button" onclick="copyCodeText(this)">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            <span>Sao chép</span>
          </button>
        </div>
        <pre><code>${escapedCode}</code></pre>
      </div>`;
    } else {
      let content = escapeHtml(block.content);
      
      // Bold: **text**
      content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      
      // Italic: *text*
      content = content.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      
      // Inline code: `code`
      content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
      
      // Blockquotes: > text
      content = content.replace(/^&gt;\s+(.*)$/gm, '<blockquote>$1</blockquote>');
      
      // Lists (unordered)
      const lines = content.split('\n');
      let inList = false;
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line.startsWith('- ') || line.startsWith('* ')) {
          const itemContent = line.slice(2);
          lines[i] = (inList ? '' : '<ul>') + `<li>${itemContent}</li>`;
          inList = true;
        } else {
          if (inList) {
            lines[i] = '</ul>' + lines[i];
            inList = false;
          }
        }
      }
      if (inList) {
        lines.push('</ul>');
      }
      content = lines.join('\n');
      
      // Convert newlines to br
      content = content.replace(/\n/g, '<br>');
      content = content.replace(/<\/blockquote><br>/g, '</blockquote>');
      content = content.replace(/<\/ul><br>/g, '</ul>');
      content = content.replace(/<ul><br>/g, '<ul>');
      
      return `<div class="text-block">${content}</div>`;
    }
  }).join('');
}

/* ==========================================================================
   RENDER FUNCTIONS
   ========================================================================== */
function renderEmptyState() {
  messages.innerHTML = `
    <section class="empty-state">
      <div class="empty-state-logo">
        <img src="avatar.png" alt="Learning OS Agent" style="width: 100%; height: 100%; object-fit: cover; border-radius: inherit;" />
      </div>
      <h2>Hôm nay bạn muốn học gì?</h2>
      <p>Hỏi về bài học, lab, rubric, khái niệm hoặc thêm tệp bằng nút đính kèm để chuẩn bị cho phần phân tích tài liệu sau này.</p>
    </section>
  `;
}

function messageTemplate(role, content, index) {
  if (typeof role === "object" && role !== null) {
    const message = role;
    const renderedContent = parseMarkdown(message.content || "");
    const followUps = Array.isArray(message.actions) && message.actions.length
      ? `<div class="follow-up-actions">${message.actions.map((action, i) => `<button type="button" data-action-index="${i}" data-message-id="${escapeHtml(message.id)}">${escapeHtml(action.label)}</button>`).join("")}</div>`
      : "";
    if (message.role === "agent") {
      return `
        <article class="message agent" data-message-id="${escapeHtml(message.id || "")}">
          <div class="avatar" aria-hidden="true">
            <img src="avatar.png" alt="Learning OS Agent" style="width: 100%; height: 100%; object-fit: cover; border-radius: inherit;" />
          </div>
          <div class="bubble">
            <div class="bubble-content">${renderedContent}</div>
            ${followUps}
            <div class="message-actions" aria-label="Hành động tin nhắn">
              <button type="button" class="action-btn like-btn" onclick="toggleLikeMessage(this)" aria-label="Thích tin nhắn">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                <span>Thích</span>
              </button>
              <div class="copy-tooltip-wrapper">
                <button type="button" class="action-btn copy-btn" onclick="copyMessageText(this, ${index})" aria-label="Sao chép tin nhắn">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                  <span>Sao chép</span>
                </button>
              </div>
              <button type="button" class="action-btn retry-btn" onclick="regenerateMessage(${index})" aria-label="Tạo lại câu trả lời">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                <span>Tạo lại</span>
              </button>
            </div>
          </div>
        </article>
      `;
    }
    const safeContent = escapeHtml(message.content || "").replace(/\n/g, "<br>");
    return `
      <article class="message user" data-message-id="${escapeHtml(message.id || "")}">
        <div class="bubble">
          <div class="bubble-content"><p>${safeContent}</p></div>
        </div>
      </article>
    `;
  }

  if (role === "agent") {
    const formattedContent = parseMarkdown(content);
    return `
      <article class="message agent">
        <div class="avatar" aria-hidden="true">
          <img src="avatar.png" alt="Learning OS Agent" style="width: 100%; height: 100%; object-fit: cover; border-radius: inherit;" />
        </div>
        <div class="bubble">
          <div class="bubble-content">${formattedContent}</div>
          <div class="message-actions" aria-label="Hành động tin nhắn">
            <button type="button" class="action-btn like-btn" onclick="toggleLikeMessage(this)" aria-label="Thích tin nhắn">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
              <span>Thích</span>
            </button>
            <div class="copy-tooltip-wrapper">
              <button type="button" class="action-btn copy-btn" onclick="copyMessageText(this, ${index})" aria-label="Sao chép tin nhắn">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                <span>Sao chép</span>
              </button>
            </div>
            <button type="button" class="action-btn retry-btn" onclick="regenerateMessage(${index})" aria-label="Tạo lại câu trả lời">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
              <span>Tạo lại</span>
            </button>
          </div>
        </div>
      </article>
    `;
  }

  const safeContent = escapeHtml(content).replace(/\n/g, '<br>');
  return `
    <article class="message user">
      <div class="bubble">
        <div class="bubble-content"><p>${safeContent}</p></div>
      </div>
    </article>
  `;
}

function renderMessages() {
  const chat = getActiveConversation();

  if (!chat || !chat.messages.length) {
    renderEmptyState();
    quickPrompts.classList.remove("hidden");
    return;
  }

  quickPrompts.classList.add("hidden");
  messages.innerHTML = chat.messages
    .map((message, index) => messageTemplate(message, null, index))
    .join("");
  scrollToBottom();
}

function renderHistory() {
  historyList.innerHTML = conversations
    .map((chat) => {
      const active = chat.id === activeId ? " active" : "";
      const escapedId = escapeHtml(chat.id);
      return `
        <div class="history-item${active}" data-chat-id="${escapedId}" onclick="switchChat('${escapedId}')">
          <div class="history-item-content">
            <strong>${escapeHtml(chat.title)}</strong>
            <span>${formatDate(chat.createdAt)}</span>
          </div>
          <div class="history-actions">
            <button class="history-btn edit-btn" onclick="renameChat(event, '${escapedId}')" title="Đổi tên" type="button" aria-label="Sửa tên">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
            </button>
            <button class="history-btn delete-btn" onclick="deleteChat(event, '${escapedId}')" title="Xóa chat" type="button" aria-label="Xóa chat">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
            </button>
          </div>
        </div>
      `;
    })
    .join("");
}

/* ==========================================================================
   GLOBAL EVENT & UTILITY HANDLERS (ATTACHED TO WINDOW)
   ========================================================================== */
window.switchChat = function(chatId) {
  activeId = chatId;
  saveState();
  renderMessages();
  renderHistory();
  setDrawer(false);
};

window.deleteChat = function(event, chatId) {
  event.stopPropagation();
  
  if (conversations.length <= 1 && conversations[0].messages.length === 0) {
    alert("Không thể xóa đoạn chat duy nhất!");
    return;
  }
  
  if (!confirm("Bạn có chắc chắn muốn xóa cuộc trò chuyện này?")) return;
  
  conversations = conversations.filter((c) => c.id !== chatId);
  
  if (conversations.length === 0) {
    conversations = [createConversation()];
  }
  
  if (activeId === chatId) {
    activeId = conversations[0].id;
  }
  
  saveState();
  renderMessages();
  renderHistory();
};

window.renameChat = function(event, chatId) {
  event.stopPropagation();
  const chat = conversations.find((c) => c.id === chatId);
  if (!chat) return;
  
  const newTitle = prompt("Nhập tiêu đề mới cho đoạn chat:", chat.title);
  if (newTitle === null) return;
  
  const trimmed = newTitle.trim();
  chat.title = trimmed || "Đoạn chat mới";
  saveState();
  renderHistory();
};

window.toggleLikeMessage = function(button) {
  button.classList.toggle("active");
  const isLiked = button.classList.contains("active");
  const span = button.querySelector("span");
  span.textContent = isLiked ? "Đã thích" : "Thích";
};

window.copyMessageText = function(button, index) {
  const chat = getActiveConversation();
  const msg = chat.messages[index];
  if (!msg) return;
  
  navigator.clipboard.writeText(msg.content).then(() => {
    let tooltip = button.closest(".copy-tooltip-wrapper").querySelector(".copy-success-tooltip");
    if (!tooltip) {
      tooltip = document.createElement("span");
      tooltip.className = "copy-success-tooltip";
      tooltip.textContent = "Đã sao chép!";
      button.closest(".copy-tooltip-wrapper").appendChild(tooltip);
    }
    
    // Force reflow
    tooltip.getBoundingClientRect();
    tooltip.classList.add("show");
    
    setTimeout(() => {
      tooltip.classList.remove("show");
    }, 1800);
  }).catch(err => {
    console.error("Lỗi khi sao chép:", err);
  });
};

window.copyCodeText = function(button) {
  const container = button.closest(".code-block-container");
  const code = container.querySelector("code");
  const text = code.innerText;
  
  navigator.clipboard.writeText(text).then(() => {
    const span = button.querySelector("span");
    const originalText = span.textContent;
    span.textContent = "Đã chép!";
    button.style.color = "var(--success-color)";
    
    setTimeout(() => {
      span.textContent = originalText;
      button.style.color = "";
    }, 1800);
  }).catch(err => {
    console.error("Lỗi khi sao chép mã code:", err);
  });
};

window.regenerateMessage = function(index) {
  const chat = getActiveConversation();
  // Find the user prompt before this agent response
  let userQuestion = "";
  for (let i = index - 1; i >= 0; i--) {
    if (chat.messages[i].role === "user") {
      userQuestion = chat.messages[i].content;
      break;
    }
  }
  
  // Remove all messages from index onwards (including this reply)
  chat.messages.splice(index);
  saveState();
  renderMessages();
  
  const targetQuestion = userQuestion || "Tải tài liệu mới";

  showTypingIndicator();
  processQuestion(targetQuestion)
    .finally(() => hideTypingIndicator());
};

/* ==========================================================================
   STATE MUTATION HELPERS
   ========================================================================== */
function addMessage(role, content, actions = []) {
  const chat = getActiveConversation();
  chat.messages.push({ id: createId(), role, content, actions });

  if (role === "user" && (chat.title === "Đoạn chat mới" || chat.title === "Doan chat moi")) {
    // Generate clean smart title from first 30 chars
    const cleanContent = content.split('\n')[0].replace(/\s+/g, " ").trim();
    chat.title = cleanContent.slice(0, 30) + (cleanContent.length > 30 ? "..." : "") || "Đoạn chat mới";
  }

  // Put active chat first in the list
  conversations = [chat].concat(conversations.filter((item) => item.id !== chat.id));
  activeId = chat.id;

  saveState();
  renderMessages();
  renderHistory();
}

function buildConversationPayload() {
  const chat = getActiveConversation();
  return chat.messages.slice(-10).map((message) => ({
    role: message.role === "agent" ? "assistant" : message.role,
    content: message.content,
  }));
}

async function loadSourceFromText(text, label) {
  if (!canUseBackend()) {
    addMessage("agent", `Mình đã nhận ${label}, nhưng backend chưa mở nên chưa thể nạp source thật.`);
    return;
  }
  try {
    const result = await apiPost("/api/source", { source: text, title: label });
    addMessage("agent", `Mình đã nạp source từ ${label}: **${result.title}**.`);
  } catch (error) {
    addMessage("agent", `Mình chưa nạp được source từ ${label}.\n\n${error.message}`);
  }
}

const readAndUploadFile = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        await loadSourceFromText(reader.result, file.name);
        resolve();
      } catch (err) {
        reject(err);
      }
    };
    reader.onerror = () => reject(reader.error);
    if (file.name.toLowerCase().endsWith(".pdf")) {
      reader.readAsDataURL(file);
    } else {
      reader.readAsText(file);
    }
  });
};

async function handleAttachedFiles(files) {
  const supportedFiles = Array.from(files).filter((file) => {
    const name = file.name.toLowerCase();
    return name.endsWith(".txt") || name.endsWith(".md") || name.endsWith(".markdown") || name.endsWith(".pdf");
  });

  for (const file of supportedFiles) {
    await readAndUploadFile(file);
  }

  const unsupported = Array.from(files).filter((file) => !supportedFiles.includes(file));
  if (unsupported.length) {
    addMessage("agent", "Hiện tại mình hỗ trợ tốt các tệp tin văn bản (.txt, .md, .markdown) và PDF (.pdf). Link GitHub hoặc web link sẽ được hỗ trợ khi bạn paste trực tiếp vào chat.");
  }
}

async function processQuestion(question) {
  if (canUseBackend()) {
    try {
      const response = await apiPost("/api/ask", {
        question,
        conversation: buildConversationPayload(),
      });
      const actions = Array.isArray(response.follow_up_options)
        ? response.follow_up_options.map((option) => ({
            label: option,
            handler: () => {
              input.value = option;
              resizeInput();
              form.requestSubmit();
            },
          }))
        : [];
      addMessage("agent", response.answer || "Mình chưa có câu trả lời phù hợp.", actions);
      return;
    } catch (error) {
      addMessage("agent", `Backend đang lỗi nên mình trả lời dự phòng nhé.\n\n${error.message}`);
      return;
    }
  }

  addMessage("agent", buildFallbackReply(question));
}

function buildFallbackReply(question) {
  const normalized = question.toLowerCase();

  if (normalized.includes("deadline") || normalized.includes("nop") || normalized.includes("repo") || normalized.includes("nộp")) {
    return `**Thông báo về Deadline & Quy định nộp bài:**

> Hiện tại phiên bản thử nghiệm **chưa có kết nối chính thức** tới nguồn dữ liệu của bạn để trích xuất deadline chính xác. 

Dưới đây là một số thông tin bạn có thể chuẩn bị sẵn:
1. **Liên kết Git Repository**: Đảm bảo cấu trúc thư mục chứa các thư mục bài làm đúng định dạng \`Day05-...\`.
2. **Commit & Push**: Hãy thường xuyên push code lên để lưu trữ.

Khi backend được tích hợp đầy đủ, hệ thống sẽ tự động quét thông tin từ hệ thống học tập để trả lời chi tiết nhất.`;
  }

  if (normalized.includes("build slice") || normalized.includes("slice nghĩa là gì")) {
    return `**Build Slice** trong phát triển phần mềm (đặc biệt là theo phương pháp Agile/Scrum) là việc xây dựng một **lát cắt dọc** (vertical slice) đầy đủ của tính năng.

Ý nghĩa của một lát cắt dọc:
- **Đầy đủ các tầng**: Đi từ giao diện người dùng (\`Frontend\`), xử lý trung gian (\`Backend\`), tới nơi lưu trữ dữ liệu (\`Database\`).
- **Chạy thử được**: Khách hàng có thể trải nghiệm trực tiếp phần tính năng này thay vì chỉ nhìn giao diện mẫu.
- **Tập trung và giảm thiểu rủi ro**: Giúp phát hiện sớm lỗi tích hợp giữa các tầng.

Ví dụ một cấu trúc file Go đơn giản khi thiết lập lát cắt dọc cho API:
\`\`\`go
package slice

import "fmt"

// UserSlice định nghĩa cấu trúc dữ liệu người dùng tinh gọn
type UserSlice struct {
    ID    string \`json:"id"\`
    Email string \`json:"email"\`
}

func GetUser(id string) (*UserSlice, error) {
    if id == "" {
        return nil, fmt.Errorf("ID không hợp lệ")
    }
    return &UserSlice{ID: id, Email: "tuananh@example.com"}, nil
}
\`\`\``;
  }

  if (normalized.includes("thin spec")) {
    return `**Thin Spec** (Tài liệu đặc tả mỏng/tinh gọn) là một bản đặc tả tính năng tối giản, tập trung vào mô tả nhanh hành vi hệ thống mà không đi sâu vào chi tiết kỹ thuật phức tạp ngay từ đầu.

Một bản **Thin Spec** chuẩn thường gồm các nội dung chính sau:
1. **Mục tiêu tính năng (Goal)**: Tại sao lại làm tính năng này? Nó giải quyết vấn đề gì?
2. **Phạm vi (Scope)**: Những gì thuộc và không thuộc tính năng ở phiên bản hiện tại.
3. **Mô tả kịch bản (User Stories)**:
   - Sử dụng cấu trúc: \`As a <role>, I want to <action> so that <benefit>\`.
   - Định nghĩa rõ các trạng thái thành công và lỗi.
4. **Tiêu chí nghiệm thu (Acceptance Criteria)**: Các điều kiện cụ thể để xác định tính năng hoàn thành.

> **Mẹo**: Hãy giữ độ dài của Thin Spec trong vòng **1-2 trang** để tối ưu hóa thời gian đọc và phản hồi nhanh từ các thành viên trong đội ngũ phát triển.`;
  }

  if (normalized.includes("bai nay") || normalized.includes("lam sao") || normalized.includes("bắt đầu") || normalized.includes("bài này")) {
    return `Để bắt đầu làm bài tập này, bạn hãy làm theo các bước tinh gọn sau:

- **Bước 1**: Đọc kỹ yêu cầu đề bài và các tiêu chí đánh giá trong file đề bài.
- **Bước 2**: Khởi tạo khung thư mục dự án của bạn (ví dụ: tạo cấu trúc file tĩnh \`index.html\`, \`styles.css\`, \`script.js\`).
- **Bước 3**: Bắt đầu triển khai phần giao diện chính trước, tập trung vào cấu trúc ngữ nghĩa (Semantic HTML).
- **Bước 4**: Thêm CSS để căn chỉnh bố cục trước khi xử lý tương tác JavaScript.

Dưới đây là một ví dụ khung HTML cơ bản nhất để bắt đầu:
\`\`\`html
<!DOCTYPE html>
<html>
<head>
  <title>Khung dự án</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div id="app"></div>
  <script src="script.js"></script>
</body>
</html>
\`\`\``;
  }

  return `Cảm ơn bạn đã trò chuyện với **Learning OS Agent**. Đây là câu trả lời được xử lý giả lập tại Frontend.

Khi có **Backend** kết nối đầy đủ, hệ thống sẽ thực hiện luồng xử lý tự động:
1. **Trích xuất ý định (Intent Detection)**: Phân tích câu hỏi của bạn.
2. **Tra cứu tài liệu (RAG - Retrieval)**: Quét cơ sở tri thức để tìm định nghĩa chính xác.
3. **Tổng hợp câu trả lời (Synthesis)**: Tạo ra phản hồi hoàn chỉnh kèm trích dẫn nguồn uy tín.

Bạn có thể thử chọn các nút gợi ý câu hỏi ở trên để xem các câu trả lời hiển thị Markdown phong phú hơn!`;
}

function resizeInput() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 140) + "px";
}

/* ==========================================================================
   FILE ATTACHMENTS LOGIC
   ========================================================================== */
function getFileIcon(fileName) {
  const ext = fileName.split('.').pop().toLowerCase();
  switch(ext) {
    case 'pdf': return '📕';
    case 'doc':
    case 'docx': return '📘';
    case 'xls':
    case 'xlsx': return '📗';
    case 'ppt':
    case 'pptx': return '📙';
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif': return '🖼️';
    case 'js':
    case 'ts':
    case 'html':
    case 'css':
    case 'py':
    case 'go':
    case 'json': return '💻';
    case 'zip':
    case 'rar': return '📦';
    default: return '📄';
  }
}

function renderSelectedFiles() {
  fileList.innerHTML = "";
  if (!selectedFiles.length) {
    fileList.classList.remove("has-files");
    return;
  }
  
  fileList.classList.add("has-files");
  selectedFiles.forEach((file, index) => {
    const chip = document.createElement("div");
    chip.className = "file-chip";
    
    const iconSpan = document.createElement("span");
    iconSpan.className = "file-chip-icon";
    iconSpan.textContent = getFileIcon(file.name);
    
    const nameSpan = document.createElement("span");
    nameSpan.className = "file-chip-name";
    nameSpan.textContent = file.name;
    
    const removeBtn = document.createElement("button");
    removeBtn.className = "file-chip-remove";
    removeBtn.type = "button";
    removeBtn.setAttribute("aria-label", "Xóa tệp");
    removeBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
    `;
    
    removeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      selectedFiles.splice(index, 1);
      renderSelectedFiles();
    });
    
    chip.appendChild(iconSpan);
    chip.appendChild(nameSpan);
    chip.appendChild(removeBtn);
    fileList.appendChild(chip);
  });
}

function showTypingIndicator() {
  if (document.getElementById("typingIndicator")) return;
  
  const indicatorHtml = `
    <article class="message agent" id="typingIndicator">
      <div class="avatar" aria-hidden="true">
        <img src="avatar.png" alt="Learning OS Agent" style="width: 100%; height: 100%; object-fit: cover; border-radius: inherit;" />
      </div>
      <div class="bubble">
        <div class="typing-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </article>
  `;
  
  quickPrompts.classList.add("hidden");
  messages.insertAdjacentHTML("beforeend", indicatorHtml);
  scrollToBottom();
}

function hideTypingIndicator() {
  const indicator = document.getElementById("typingIndicator");
  if (indicator) {
    indicator.remove();
  }
}

function createNewChat() {
  const chat = createConversation();
  conversations = [chat].concat(conversations);
  activeId = chat.id;
  selectedFiles = [];
  renderSelectedFiles();
  saveState();
  renderMessages();
  renderHistory();
  setDrawer(false);
  input.focus();
}

/* ==========================================================================
   EVENT LISTENERS
   ========================================================================== */
menuButton.addEventListener("click", () => setDrawer(true));
closeDrawer.addEventListener("click", () => setDrawer(false));
drawerBackdrop.addEventListener("click", () => setDrawer(false));
newChatButton.addEventListener("click", createNewChat);
headerNewChatButton.addEventListener("click", createNewChat);

attachButton.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", () => {
  Array.from(fileInput.files).forEach((file) => {
    // Avoid duplicates
    if (!selectedFiles.some((f) => f.name === file.name && f.size === file.size)) {
      selectedFiles.push(file);
    }
  });
  fileInput.value = ""; // Reset so same file can trigger change again
  renderSelectedFiles();
});

input.addEventListener("input", resizeInput);

// Handle Enter to Submit (while Shift+Enter inserts newline)
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});



form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const question = input.value.trim();
  if (!question && !selectedFiles.length) return;

  const fileNames = selectedFiles.map((file) => file.name);
  const userText = fileNames.length
    ? (question ? question + "\n\n" : "") + "📁 **Tệp đính kèm:** " + fileNames.join(", ")
    : question;

  addMessage("user", userText);
  input.value = "";
  resizeInput();

  const filesToProcess = [...selectedFiles];
  selectedFiles = [];
  renderSelectedFiles();

  showTypingIndicator();
  try {
    if (filesToProcess.length) {
      await handleAttachedFiles(filesToProcess);
    }
    if (question) {
      await processQuestion(question);
    }
  } finally {
    hideTypingIndicator();
  }
});

messages.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action-index]");
  if (!button) return;

  const messageId = button.getAttribute("data-message-id");
  const actionIndex = Number(button.getAttribute("data-action-index"));
  const chat = getActiveConversation();
  const message = chat.messages.find((item) => item.id === messageId);
  const action = message && message.actions ? message.actions[actionIndex] : null;
  if (action && typeof action.handler === "function") {
    action.handler();
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.prompt;
    resizeInput();
    input.focus();
  });
});

/* ==========================================================================
   INITIALIZATION
   ========================================================================== */
initTheme();
saveState();
renderMessages();
renderHistory();
