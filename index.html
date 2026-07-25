<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CHOTU AI - Advanced Chatbot Interface</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    :root {
      --primary: #FF6B6B;
      --secondary: #4ECDC4;
      --accent: #FFE66D;
      --dark: #0f1419;
      --darker: #0a0d12;
      --light: #f5f7fa;
      --text-primary: #e8eef2;
      --text-secondary: #a8b2bf;
      --border: #1e2835;
      --success: #00d66a;
      --warning: #ffa500;
      --error: #ff5555;
    }

    body {
      font-family: 'Inter', sans-serif;
      background: linear-gradient(135deg, var(--darker) 0%, var(--dark) 100%);
      color: var(--text-primary);
      overflow: hidden;
      height: 100vh;
    }

    .chatbot-container {
      display: flex;
      height: 100vh;
      background: var(--dark);
    }

    /* SIDEBAR */
    .sidebar {
      width: 300px;
      background: var(--darker);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }

    .sidebar-header {
      padding: 20px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .logo {
      font-size: 20px;
      font-weight: 700;
      color: var(--primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .logo-icon {
      font-size: 24px;
    }

    .new-chat-btn {
      background: var(--primary);
      color: white;
      border: none;
      padding: 8px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.3s;
      font-size: 12px;
    }

    .new-chat-btn:hover {
      background: #ff5252;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(255, 107, 107, 0.3);
    }

    .conversation-list {
      flex: 1;
      overflow-y: auto;
      padding: 12px;
    }

    .conversation-item {
      padding: 12px;
      margin-bottom: 8px;
      background: rgba(78, 205, 196, 0.05);
      border: 1px solid transparent;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.3s;
      font-size: 13px;
      color: var(--text-secondary);
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }

    .conversation-item:hover {
      background: rgba(78, 205, 196, 0.1);
      border-color: var(--secondary);
      color: var(--text-primary);
    }

    .conversation-item.active {
      background: rgba(255, 107, 107, 0.1);
      border-color: var(--primary);
      color: var(--primary);
      font-weight: 600;
    }

    .sidebar-footer {
      padding: 16px;
      border-top: 1px solid var(--border);
      display: flex;
      gap: 8px;
    }

    .sidebar-footer button {
      flex: 1;
      padding: 10px;
      background: rgba(255, 107, 107, 0.1);
      border: 1px solid var(--border);
      color: var(--text-secondary);
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.3s;
      font-size: 12px;
    }

    .sidebar-footer button:hover {
      background: rgba(255, 107, 107, 0.2);
      color: var(--primary);
    }

    /* MAIN CHAT AREA */
    .chat-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      background: var(--dark);
    }

    .chat-header {
      padding: 16px 24px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: linear-gradient(180deg, rgba(78, 205, 196, 0.05) 0%, transparent 100%);
    }

    .chat-title {
      font-weight: 600;
      color: var(--text-primary);
    }

    .chat-title-sub {
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 4px;
    }

    .chat-actions {
      display: flex;
      gap: 12px;
    }

    .icon-btn {
      width: 36px;
      height: 36px;
      border: 1px solid var(--border);
      background: transparent;
      color: var(--text-secondary);
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.3s;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
    }

    .icon-btn:hover {
      background: rgba(78, 205, 196, 0.1);
      border-color: var(--secondary);
      color: var(--secondary);
    }

    /* MESSAGES */
    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .message-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
      animation: slideUp 0.3s ease-out;
    }

    @keyframes slideUp {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .message {
      display: flex;
      align-items: flex-end;
      gap: 12px;
    }

    .message.user {
      justify-content: flex-end;
    }

    .message.ai {
      justify-content: flex-start;
    }

    .avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 14px;
      flex-shrink: 0;
    }

    .avatar.user {
      background: linear-gradient(135deg, var(--primary), #ff8787);
      color: white;
    }

    .avatar.ai {
      background: linear-gradient(135deg, var(--secondary), #26a896);
      color: white;
    }

    .message-bubble {
      max-width: 60%;
      padding: 12px 16px;
      border-radius: 12px;
      word-wrap: break-word;
      line-height: 1.5;
      font-size: 14px;
    }

    .message.user .message-bubble {
      background: linear-gradient(135deg, var(--primary), #ff8787);
      color: white;
      border-bottom-right-radius: 4px;
    }

    .message.ai .message-bubble {
      background: var(--darker);
      color: var(--text-primary);
      border: 1px solid var(--border);
      border-bottom-left-radius: 4px;
    }

    .message-time {
      font-size: 11px;
      color: var(--text-secondary);
      margin-top: 4px;
    }

    .message-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;
      font-size: 12px;
    }

    .confidence-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 8px;
      background: rgba(0, 214, 106, 0.15);
      color: var(--success);
      border-radius: 4px;
      border: 1px solid rgba(0, 214, 106, 0.3);
    }

    .source-link {
      color: var(--secondary);
      text-decoration: none;
      border-bottom: 1px dotted var(--secondary);
      cursor: pointer;
      transition: color 0.3s;
    }

    .source-link:hover {
      color: var(--accent);
    }

    .loading-indicator {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text-secondary);
      font-size: 13px;
    }

    .typing-dots {
      display: flex;
      gap: 4px;
    }

    .dot {
      width: 6px;
      height: 6px;
      background: var(--secondary);
      border-radius: 50%;
      animation: bounce 1.4s infinite;
    }

    .dot:nth-child(2) {
      animation-delay: 0.2s;
    }

    .dot:nth-child(3) {
      animation-delay: 0.4s;
    }

    @keyframes bounce {
      0%, 80%, 100% { transform: translateY(0); }
      40% { transform: translateY(-8px); }
    }

    /* INPUT AREA */
    .input-area {
      padding: 20px 24px;
      border-top: 1px solid var(--border);
      background: linear-gradient(180deg, transparent 0%, rgba(78, 205, 196, 0.02) 100%);
    }

    .input-wrapper {
      display: flex;
      gap: 12px;
      margin-bottom: 12px;
    }

    .file-upload-btn {
      width: 40px;
      height: 40px;
      background: rgba(78, 205, 196, 0.1);
      border: 1px solid var(--secondary);
      color: var(--secondary);
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s;
      font-size: 18px;
    }

    .file-upload-btn:hover {
      background: rgba(78, 205, 196, 0.2);
    }

    .input-field {
      flex: 1;
      background: var(--darker);
      border: 1px solid var(--border);
      color: var(--text-primary);
      padding: 12px 16px;
      border-radius: 8px;
      font-family: 'Inter', sans-serif;
      font-size: 14px;
      resize: none;
      max-height: 100px;
      transition: all 0.3s;
    }

    .input-field:focus {
      outline: none;
      border-color: var(--secondary);
      box-shadow: 0 0 0 2px rgba(78, 205, 196, 0.1);
    }

    .input-field::placeholder {
      color: var(--text-secondary);
    }

    .send-btn {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, var(--primary), #ff8787);
      border: none;
      color: white;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      transition: all 0.3s;
      font-weight: 600;
    }

    .send-btn:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 6px 16px rgba(255, 107, 107, 0.3);
    }

    .send-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .input-helper {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .quick-action {
      padding: 6px 12px;
      background: rgba(78, 205, 196, 0.1);
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.3s;
      color: var(--text-secondary);
    }

    .quick-action:hover {
      background: rgba(78, 205, 196, 0.2);
      border-color: var(--secondary);
      color: var(--secondary);
    }

    /* SCROLLBAR */
    ::-webkit-scrollbar {
      width: 6px;
    }

    ::-webkit-scrollbar-track {
      background: transparent;
    }

    ::-webkit-scrollbar-thumb {
      background: var(--border);
      border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
      background: rgba(78, 205, 196, 0.4);
    }

    /* MODAL */
    .modal {
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.8);
      z-index: 1000;
      align-items: center;
      justify-content: center;
    }

    .modal.active {
      display: flex;
    }

    .modal-content {
      background: var(--darker);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      max-width: 500px;
      width: 90%;
      max-height: 80vh;
      overflow-y: auto;
    }

    .modal-header {
      font-size: 20px;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 16px;
    }

    .modal-close {
      position: absolute;
      top: 16px;
      right: 16px;
      background: none;
      border: none;
      color: var(--text-secondary);
      font-size: 24px;
      cursor: pointer;
      transition: color 0.3s;
    }

    .modal-close:hover {
      color: var(--primary);
    }

    /* RESPONSIVE */
    @media (max-width: 768px) {
      .sidebar {
        width: 260px;
      }

      .message-bubble {
        max-width: 80%;
      }

      .chat-header {
        padding: 12px 16px;
      }

      .messages-container {
        padding: 16px;
      }

      .input-area {
        padding: 16px;
      }
    }

    @media (max-width: 640px) {
      .sidebar {
        position: absolute;
        left: 0;
        top: 0;
        height: 100%;
        z-index: 100;
        transform: translateX(-100%);
        transition: transform 0.3s;
      }

      .sidebar.open {
        transform: translateX(0);
      }

      .toggle-sidebar {
        display: block;
      }

      .message-bubble {
        max-width: 90%;
      }
    }
  </style>
</head>
<body>

<div class="chatbot-container">
  
  <!-- SIDEBAR -->
  <div class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <span class="logo-icon">🎓</span>
        <span>CHOTU</span>
      </div>
      <button class="new-chat-btn" onclick="newChat()">+ New</button>
    </div>

    <div class="conversation-list" id="conversationList">
      <div class="conversation-item active">📚 Physics Help</div>
      <div class="conversation-item">🧪 Chemistry Quiz</div>
      <div class="conversation-item">📖 History Essay</div>
      <div class="conversation-item">🔢 Math Problems</div>
      <div class="conversation-item">💻 Programming Tips</div>
    </div>

    <div class="sidebar-footer">
      <button onclick="showSettings()">⚙️ Settings</button>
      <button onclick="logout()">🚪 Logout</button>
    </div>
  </div>

  <!-- MAIN CHAT -->
  <div class="chat-main">
    
    <!-- HEADER -->
    <div class="chat-header">
      <div>
        <div class="chat-title">📚 Physics Help</div>
        <div class="chat-title-sub">AI study assistant</div>
      </div>
      <div class="chat-actions">
        <button class="icon-btn" onclick="downloadChat()">⬇️</button>
        <button class="icon-btn" onclick="shareChat()">📤</button>
        <button class="icon-btn" onclick="toggleSettings()">⚙️</button>
      </div>
    </div>

    <!-- MESSAGES -->
    <div class="messages-container" id="messagesContainer">
      
      <!-- Welcome Message -->
      <div style="text-align: center; padding: 40px 20px; color: var(--text-secondary);">
        <div style="font-size: 40px; margin-bottom: 12px;">🤖</div>
        <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">Welcome to CHOTU AI</div>
        <div style="font-size: 13px; max-width: 400px;">Your personal AI study assistant. Upload PDFs, ask questions, and get instant explanations. Answers are generated live — nothing on this screen is pre-written.</div>
      </div>

    </div>

    <!-- INPUT AREA -->
    <div class="input-area">
      <div class="input-wrapper">
        <input type="file" id="pdfFileInput" accept="application/pdf" style="display:none" onchange="handlePdfSelected(event)"/>
        <button class="file-upload-btn" onclick="uploadPDF()">📤</button>
        <textarea 
          class="input-field" 
          id="messageInput"
          placeholder="Ask me anything... (Shift+Enter for new line)"
          rows="2"
        ></textarea>
        <button class="send-btn" onclick="sendMessage()">➤</button>
      </div>

      <div class="input-helper">
        <span>Quick actions:</span>
        <button class="quick-action" onclick="quickAsk('Explain this concept')">💡 Explain</button>
        <button class="quick-action" onclick="quickAsk('Generate practice problems')">🎯 Practice</button>
        <button class="quick-action" onclick="quickAsk('Quiz me')">🧠 Quiz</button>
        <button class="quick-action" onclick="quickAsk('Create study plan')">📅 Plan</button>
      </div>
    </div>

  </div>

</div>

<!-- SETTINGS MODAL -->
<div class="modal" id="settingsModal">
  <div class="modal-content">
    <button class="modal-close" onclick="toggleSettings()">✕</button>
    <div class="modal-header">⚙️ Settings</div>
    
    <div style="margin-bottom: 24px;">
      <div style="font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">AI Model</div>
      <select style="width: 100%; padding: 8px; background: var(--darker); border: 1px solid var(--border); color: var(--text-primary); border-radius: 6px;">
        <option>Groq Mixtral 8x7b (Fast)</option>
        <option>GPT-4 (Most Accurate)</option>
        <option>Local LLaMA (Private)</option>
      </select>
    </div>

    <div style="margin-bottom: 24px;">
      <div style="font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">Response Length</div>
      <div style="display: flex; gap: 12px;">
        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
          <input type="radio" name="length" checked>
          <span>Concise</span>
        </label>
        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
          <input type="radio" name="length">
          <span>Detailed</span>
        </label>
      </div>
    </div>

    <div style="margin-bottom: 24px;">
      <div style="font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">Learning Style</div>
      <select style="width: 100%; padding: 8px; background: var(--darker); border: 1px solid var(--border); color: var(--text-primary); border-radius: 6px;">
        <option>Visual Learner</option>
        <option>Auditory Learner</option>
        <option>Reading/Writing</option>
        <option>Kinesthetic</option>
      </select>
    </div>

    <button style="width: 100%; padding: 12px; background: linear-gradient(135deg, var(--primary), #ff8787); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;" onclick="toggleSettings()">Save Settings</button>
  </div>
</div>

<script>
  // Auto-resize textarea
  const textarea = document.getElementById('messageInput');
  textarea.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 100) + 'px';
  });

  // Send message on Enter
  textarea.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    if (!message) return;

    const token = localStorage.getItem('chotu_token');
    if (!token) {
      window.location.href = '/login.html';
      return;
    }

    addMessage(message, 'user');
    input.value = '';
    input.style.height = 'auto';

    try {
      const response = await fetch('/chat/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ question: message })
      });

      if (response.status === 401) {
        localStorage.removeItem('chotu_token');
        window.location.href = '/login.html';
        return;
      }

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`${response.status}: ${errText}`);
      }

      const data = await response.json();
      addMessage(data.answer, 'ai');
    } catch (err) {
      addMessage(`⚠️ Failed to reach Chotu: ${err.message}`, 'ai');
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function addMessage(text, sender) {
    const container = document.getElementById('messagesContainer');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;

    const avatar = sender === 'user' ? '👤' : '🤖';
    const avatarClass = sender === 'user' ? 'user' : 'ai';
    const safeText = escapeHtml(text).replace(/\n/g, '<br>');

    msgDiv.innerHTML = `
      <div class="${sender === 'user' ? '' : 'avatar ' + avatarClass}${sender === 'user' ? '' : ''}">
        ${sender === 'user' ? '' : avatar}
      </div>
      <div>
        <div class="message-bubble">${safeText}</div>
        <div class="message-time" style="${sender === 'user' ? 'text-align: right;' : ''}">${new Date().toLocaleTimeString()}</div>
      </div>
      ${sender === 'user' ? `<div class="avatar ${avatarClass}">${avatar}</div>` : ''}
    `;

    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
  }

  function quickAsk(action) {
    document.getElementById('messageInput').value = action;
    sendMessage();
  }

  function uploadPDF() {
    const token = localStorage.getItem('chotu_token');
    if (!token) {
      window.location.href = '/login.html';
      return;
    }
    document.getElementById('pdfFileInput').click();
  }

  async function handlePdfSelected(event) {
    const file = event.target.files[0];
    event.target.value = ''; // allow re-selecting the same file later
    if (!file) return;

    const token = localStorage.getItem('chotu_token');
    addMessage(`Uploading ${file.name}...`, 'user');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/upload/pdf', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });

      if (response.status === 401) {
        localStorage.removeItem('chotu_token');
        window.location.href = '/login.html';
        return;
      }

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`${response.status}: ${errText}`);
      }

      const data = await response.json();
      addMessage(`Uploaded and processed "${file.name}" — ${data.chunks} chunks extracted. You can ask questions about it now.`, 'ai');
    } catch (err) {
      addMessage(`⚠️ Upload failed: ${err.message}`, 'ai');
    }
  }

  function newChat() {
    document.getElementById('messagesContainer').innerHTML = `
      <div style="text-align: center; padding: 40px 20px; color: var(--text-secondary);">
        <div style="font-size: 40px; margin-bottom: 12px;">🎓</div>
        <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">New Conversation</div>
        <div style="font-size: 13px;">Start by uploading a PDF or asking a question</div>
      </div>
    `;
  }

  function toggleSettings() {
    document.getElementById('settingsModal').classList.toggle('active');
  }

  function showSettings() {
    toggleSettings();
  }

  function downloadChat() {
    alert('Download chat is not built yet.');
  }

  function shareChat() {
    alert('Share chat is not built yet.');
  }

  async function logout() {
    if (!confirm('Are you sure you want to logout?')) return;
    const token = localStorage.getItem('chotu_token');
    try {
      if (token) {
        await fetch('/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
      }
    } catch (err) {
      // even if the server call fails, still clear locally so the user isn't stuck
    }
    localStorage.removeItem('chotu_token');
    localStorage.removeItem('chotu_user');
    window.location.href = '/login.html';
  }
</script>

</body>
</html>
