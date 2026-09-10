(() => {
	const script = document.currentScript;
	const websiteId = script && script.dataset.websiteId;
	if (!websiteId) return;

	const apiBase = new URL(script.src, window.location.href).origin;
	const inlineLogoUrl = (script && script.dataset.logoUrl) || null;
	const inlinePrimaryColor = (script && script.dataset.primaryColor) || null;
	const inlineSiteUrl = (script && script.dataset.siteUrl) || null;

	// ── Fetch brand config then build ────────────────────────────────────────
	fetch(`${apiBase}/api/website/${websiteId}/config`)
		.then(r => r.ok ? r.json() : Promise.reject())
		.catch(() => ({ name: "Support", url: inlineSiteUrl, logo_url: null, primary_color: "#17191d" }))
		.then(config => {
			if (inlineLogoUrl) config.logo_url = inlineLogoUrl;
			if (inlinePrimaryColor) config.primary_color = inlinePrimaryColor;
			if (inlineSiteUrl) config.url = inlineSiteUrl;
			buildWidget(config);
		});

	// ─────────────────────────────────────────────────────────────────────────
	function buildWidget({ name, url, logo_url, primary_color }) {

		// ── Color system ─────────────────────────────────────────────────────
		const accent     = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(primary_color || "")
		                   ? primary_color : "#17191d";
		const light      = isLight(accent);
		const fg         = light ? "#1a1a1a" : "#ffffff";           // text on accent
		const accentDark = adjustBrightness(accent, light ? -30 : -25);
		const accentSoft = hexToRgba(accent, 0.12);                 // very faint tint
		const brandLogo = logo_url || faviconUrl(url);

		// ── Inject styles ────────────────────────────────────────────────────
		const style = document.createElement("style");
		style.textContent = `
		@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

		/* ── Launcher ── */
		.eiq-btn {
		  position: fixed; right: 24px; bottom: 24px; z-index: 2147483646;
		  border: none; border-radius: 50%;
		  width: 60px; height: 60px;
		  background: ${accent};
		  box-shadow: 0 4px 16px ${hexToRgba(accent, 0.55)}, 0 2px 6px rgba(0,0,0,0.25);
		  cursor: pointer;
		  display: flex; align-items: center; justify-content: center;
		  padding: 0; overflow: hidden;
		  transition: transform .2s ease, box-shadow .2s ease;
		}
		.eiq-btn:hover {
		  transform: scale(1.1);
		  box-shadow: 0 6px 24px ${hexToRgba(accent, 0.65)}, 0 3px 8px rgba(0,0,0,0.3);
		}
		.eiq-btn:active { transform: scale(0.96); }
		.eiq-btn-logo {
		  width: 100%; height: 100%; border-radius: 50%;
		  object-fit: cover;
		}
		.eiq-btn svg { width: 28px; height: 28px; fill: ${fg}; }

		/* ── Panel ── */
		.eiq-panel {
		  position: fixed; right: 24px; bottom: 96px; z-index: 2147483647;
		  width: min(370px, calc(100vw - 28px));
		  height: min(560px, calc(100vh - 120px));
		  display: none; flex-direction: column;
		  border-radius: 18px; overflow: hidden;
		  box-shadow: 0 24px 64px rgba(0,0,0,0.22), 0 4px 16px rgba(0,0,0,0.12);
		  font-family: 'Inter', system-ui, -apple-system, sans-serif;
		  background: #ffffff;
		  border: 1px solid rgba(0,0,0,0.07);
		}
		.eiq-panel.eiq-open {
		  display: flex;
		  animation: eiq-up .22s cubic-bezier(.34,1.4,.64,1);
		}
		@keyframes eiq-up {
		  from { opacity: 0; transform: translateY(20px) scale(.97); }
		  to   { opacity: 1; transform: translateY(0)   scale(1);    }
		}

		/* ── Header ── */
		.eiq-head {
		  background: ${accent};
		  padding: 14px 16px 13px;
		  display: flex; align-items: center; gap: 11px;
		  flex-shrink: 0;
		  position: relative;
		}
		.eiq-head-avatar {
		  width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0;
		  background: ${fg === '#ffffff' ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.1)'};
		  display: flex; align-items: center; justify-content: center;
		  overflow: hidden;
		  border: 2px solid ${fg === '#ffffff' ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.15)'};
		}
		.eiq-head-avatar img {
		  width: 100%; height: 100%; object-fit: contain; padding: 5px;
		  border-radius: 50%;
		}
		.eiq-head-avatar svg { width: 22px; height: 22px; fill: ${fg}; }
		.eiq-head-info { flex: 1; min-width: 0; }
		.eiq-head-name {
		  font-size: 15px; font-weight: 700;
		  color: ${fg}; line-height: 1.2;
		  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		}
		.eiq-head-status {
		  font-size: 11px; color: ${fg};
		  opacity: .78; margin-top: 2px;
		  display: flex; align-items: center; gap: 4px;
		}
		.eiq-status-dot {
		  width: 7px; height: 7px; border-radius: 50%;
		  background: ${light ? '#2ecc71' : '#4ade80'};
		  box-shadow: 0 0 0 2px ${hexToRgba(light ? '#2ecc71' : '#4ade80', 0.3)};
		  flex-shrink: 0;
		}
		.eiq-close {
		  background: ${fg === '#ffffff' ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.08)'};
		  border: none; border-radius: 50%;
		  width: 30px; height: 30px;
		  color: ${fg}; cursor: pointer; font-size: 16px;
		  display: flex; align-items: center; justify-content: center;
		  transition: background .15s; flex-shrink: 0;
		}
		.eiq-close:hover {
		  background: ${fg === '#ffffff' ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.16)'};
		}

		/* ── Messages area ── */
		.eiq-msgs {
		  flex: 1; padding: 16px 14px; overflow-y: auto;
		  background: #f8f9fb;
		  display: flex; flex-direction: column; gap: 10px;
		  scroll-behavior: smooth;
		}
		.eiq-msgs::-webkit-scrollbar { width: 4px; }
		.eiq-msgs::-webkit-scrollbar-track { background: transparent; }
		.eiq-msgs::-webkit-scrollbar-thumb { background: #ddd; border-radius: 2px; }

		/* ── Message bubbles ── */
		.eiq-msg {
		  max-width: 84%; padding: 10px 14px;
		  line-height: 1.55; font-size: 13.5px;
		  word-break: break-word; white-space: pre-wrap;
		}
		.eiq-bot {
		  background: #ffffff; color: #1f2937;
		  border: 1px solid #e5e7eb;
		  border-radius: 16px 16px 16px 4px;
		  align-self: flex-start;
		  border-left: 3px solid ${accent};
		  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
		}
		.eiq-user {
		  background: ${accent}; color: ${fg};
		  border-radius: 16px 16px 4px 16px;
		  align-self: flex-end;
		  box-shadow: 0 2px 8px ${hexToRgba(accent, 0.3)};
		}

		/* ── Typing dots ── */
		.eiq-typing {
		  background: #ffffff; border: 1px solid #e5e7eb;
		  border-radius: 16px 16px 16px 4px;
		  border-left: 3px solid ${accent};
		  padding: 12px 16px; align-self: flex-start;
		  display: flex; align-items: center; gap: 4px;
		}
		.eiq-typing span {
		  width: 7px; height: 7px; border-radius: 50%;
		  background: ${accent}; opacity: .6;
		  animation: eiq-dot .9s ease-in-out infinite;
		}
		.eiq-typing span:nth-child(2) { animation-delay: .18s; }
		.eiq-typing span:nth-child(3) { animation-delay: .36s; }
		@keyframes eiq-dot {
		  0%,60%,100% { transform: translateY(0);   opacity: .4; }
		  30%          { transform: translateY(-5px); opacity: 1;  }
		}

		/* ── Input area ── */
		.eiq-footer {
		  background: #ffffff;
		  border-top: 1px solid #f0f0f0;
		  padding: 10px 12px;
		  display: flex; gap: 8px; align-items: flex-end;
		  flex-shrink: 0;
		}
		.eiq-input {
		  flex: 1; min-height: 38px; max-height: 100px;
		  padding: 9px 13px;
		  border: 1.5px solid #e5e7eb; border-radius: 12px;
		  font-family: inherit; font-size: 13.5px; color: #1f2937;
		  background: #f9fafb;
		  outline: none; resize: none;
		  transition: border-color .2s, background .2s;
		  line-height: 1.4;
		  overflow-y: auto;
		}
		.eiq-input:focus {
		  border-color: ${accent};
		  background: #ffffff;
		  box-shadow: 0 0 0 3px ${accentSoft};
		}
		.eiq-input::placeholder { color: #9ca3af; }
		.eiq-send {
		  width: 38px; height: 38px; flex-shrink: 0;
		  border: none; border-radius: 10px;
		  background: ${accent}; color: ${fg};
		  cursor: pointer; display: flex; align-items: center; justify-content: center;
		  transition: background .2s, transform .1s;
		}
		.eiq-send:hover { background: ${accentDark}; }
		.eiq-send:active { transform: scale(.93); }
		.eiq-send svg { width: 17px; height: 17px; fill: ${fg}; }
		.eiq-send:disabled { opacity: .45; cursor: not-allowed; }

		/* ── Powered by ── */
		.eiq-powered {
		  text-align: center; font-size: 10px; color: #9ca3af;
		  padding: 5px 0 7px; background: #ffffff;
		  flex-shrink: 0; letter-spacing: .02em;
		}
		.eiq-powered a { color: ${accent}; text-decoration: none; font-weight: 600; }
		`;
		document.head.appendChild(style);

		// ── Launcher ─────────────────────────────────────────────────────────
		const btn = document.createElement("button");
		btn.className = "eiq-btn";
		btn.setAttribute("aria-label", `Chat with ${name || "us"}`);
		btn.setAttribute("title",      `Chat with ${name || "us"}`);

		if (brandLogo) {
			const img = document.createElement("img");
			img.className = "eiq-btn-logo";
			img.src = brandLogo;
			img.alt = name || "Logo";
			img.onerror = () => { img.replaceWith(chatIconSvg()); };
			btn.appendChild(img);
		} else {
			btn.appendChild(chatIconSvg());
		}

		// ── Panel ────────────────────────────────────────────────────────────
		const panel = document.createElement("section");
		panel.className = "eiq-panel";
		panel.setAttribute("role", "dialog");
		panel.setAttribute("aria-label", `${name || "Support"} chat`);

		// Header
		const head = document.createElement("div");
		head.className = "eiq-head";

		const avatar = document.createElement("div");
		avatar.className = "eiq-head-avatar";
		if (brandLogo) {
			const hImg = document.createElement("img");
			hImg.src = brandLogo;
			hImg.alt = name || "Logo";
			hImg.onerror = () => { hImg.replaceWith(chatIconSvgColored(fg)); };
			avatar.appendChild(hImg);
		} else {
			avatar.appendChild(chatIconSvgColored(fg));
		}

		const info = document.createElement("div");
		info.className = "eiq-head-info";

		const hName = document.createElement("div");
		hName.className = "eiq-head-name";
		hName.textContent = name || "Support";

		const hStatus = document.createElement("div");
		hStatus.className = "eiq-head-status";
		const dot = document.createElement("span");
		dot.className = "eiq-status-dot";
		hStatus.appendChild(dot);
		hStatus.appendChild(document.createTextNode("Online • AI Assistant"));

		info.append(hName, hStatus);

		const closeBtn = document.createElement("button");
		closeBtn.className = "eiq-close";
		closeBtn.setAttribute("aria-label", "Close chat");
		closeBtn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;
		closeBtn.onclick = () => panel.classList.remove("eiq-open");

		head.append(avatar, info, closeBtn);

		// Messages
		const msgs = document.createElement("div");
		msgs.className = "eiq-msgs";
		addBotMsg(msgs, `Hi! I'm the ${name || "Support"} assistant. How can I help you today?`);

		// Footer
		const footer = document.createElement("div");
		footer.className = "eiq-footer";

		const input = document.createElement("textarea");
		input.className = "eiq-input";
		input.placeholder = "Type a message…";
		input.rows = 1;
		input.setAttribute("aria-label", "Your message");

		// Auto-resize textarea
		input.addEventListener("input", () => {
			input.style.height = "auto";
			input.style.height = Math.min(input.scrollHeight, 100) + "px";
		});
		// Send on Enter (Shift+Enter = newline)
		input.addEventListener("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				sendMessage();
			}
		});

		const sendBtn = document.createElement("button");
		sendBtn.className = "eiq-send";
		sendBtn.setAttribute("aria-label", "Send");
		sendBtn.type = "button";
		sendBtn.innerHTML = `<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
		sendBtn.onclick = sendMessage;

		footer.append(input, sendBtn);

		// Powered by
		const powered = document.createElement("div");
		powered.className = "eiq-powered";
		powered.innerHTML = `Powered by <a href="#" tabindex="-1">EMBEDD IQ</a>`;

		panel.append(head, msgs, footer, powered);
		document.body.append(btn, panel);

		// ── Toggle ───────────────────────────────────────────────────────────
		btn.onclick = () => {
			const isOpen = panel.classList.contains("eiq-open");
			if (isOpen) {
				panel.classList.remove("eiq-open");
			} else {
				panel.classList.add("eiq-open");
				setTimeout(() => input.focus(), 50);
			}
		};

		// ── Send message ─────────────────────────────────────────────────────
		async function sendMessage() {
			const query = input.value.trim();
			if (!query || sendBtn.disabled) return;

			input.value = "";
			input.style.height = "auto";
			sendBtn.disabled = true;
			addUserMsg(msgs, query);

			const typing = addTyping(msgs);
			try {
				const res  = await fetch(`${apiBase}/api/chat`, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ website_id: websiteId, query })
				});
				const data = await res.json();
				typing.remove();
				addBotMsg(msgs, res.ok ? data.answer : "Sorry, I couldn't answer that right now.");
			} catch (_) {
				typing.remove();
				addBotMsg(msgs, "Connection error. Please try again.");
			} finally {
				sendBtn.disabled = false;
				input.focus();
			}
		}
	}

	// ── Message helpers ───────────────────────────────────────────────────────
	function addBotMsg(container, text) {
		const d = document.createElement("div");
		d.className = "eiq-msg eiq-bot";
		d.textContent = text;
		container.appendChild(d);
		container.scrollTop = container.scrollHeight;
		return d;
	}
	function addUserMsg(container, text) {
		const d = document.createElement("div");
		d.className = "eiq-msg eiq-user";
		d.textContent = text;
		container.appendChild(d);
		container.scrollTop = container.scrollHeight;
		return d;
	}
	function addTyping(container) {
		const d = document.createElement("div");
		d.className = "eiq-typing";
		d.innerHTML = "<span></span><span></span><span></span>";
		container.appendChild(d);
		container.scrollTop = container.scrollHeight;
		return d;
	}

	function faviconUrl(siteUrl) {
		try {
			return `${new URL(siteUrl).origin}/favicon.ico`;
		} catch (_) {
			return null;
		}
	}

	// ── SVG icons ─────────────────────────────────────────────────────────────
	function chatIconSvg() {
		const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
		s.setAttribute("viewBox", "0 0 24 24");
		s.setAttribute("width", "28"); s.setAttribute("height", "28");
		s.style.fill = "#ffffff";
		s.innerHTML = '<path d="M20 2H4C2.9 2 2 2.9 2 4v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>';
		return s;
	}
	function chatIconSvgColored(fill) {
		const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
		s.setAttribute("viewBox", "0 0 24 24");
		s.setAttribute("width", "20"); s.setAttribute("height", "20");
		s.style.fill = fill;
		s.innerHTML = '<path d="M20 2H4C2.9 2 2 2.9 2 4v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>';
		return s;
	}

	// ── Color utilities ───────────────────────────────────────────────────────
	function isLight(hex) {
		const c = hex.replace("#", "");
		const r = parseInt(c.length === 3 ? c[0]+c[0] : c.slice(0,2), 16);
		const g = parseInt(c.length === 3 ? c[1]+c[1] : c.slice(2,4), 16);
		const b = parseInt(c.length === 3 ? c[2]+c[2] : c.slice(4,6), 16);
		return (r*299 + g*587 + b*114) / 1000 > 155;
	}
	function adjustBrightness(hex, amount) {
		const c = hex.replace("#", "");
		let r = parseInt(c.length === 3 ? c[0]+c[0] : c.slice(0,2), 16);
		let g = parseInt(c.length === 3 ? c[1]+c[1] : c.slice(2,4), 16);
		let b = parseInt(c.length === 3 ? c[2]+c[2] : c.slice(4,6), 16);
		r = Math.min(255, Math.max(0, r + amount));
		g = Math.min(255, Math.max(0, g + amount));
		b = Math.min(255, Math.max(0, b + amount));
		return `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}`;
	}
	function hexToRgba(hex, alpha) {
		const c = hex.replace("#", "");
		const r = parseInt(c.length === 3 ? c[0]+c[0] : c.slice(0,2), 16);
		const g = parseInt(c.length === 3 ? c[1]+c[1] : c.slice(2,4), 16);
		const b = parseInt(c.length === 3 ? c[2]+c[2] : c.slice(4,6), 16);
		return `rgba(${r},${g},${b},${alpha})`;
	}
})();
