/* ============================================================
   欧阳聚德招投标系统 — 共享脚本
   ============================================================ */

/* ========== 登录态 SRMAuth ==========
   localStorage存token+user;srmFetch自动带Authorization;
   requireAuth未登录跳login;initAuthNav根据登录态渲染右上角
*/
window.SRMAuth = (function () {
    const TK = "srm_token", UK = "srm_user";
    return {
        getToken: () => localStorage.getItem(TK),
        setToken: (t) => localStorage.setItem(TK, t),
        getUser: () => {
            try { return JSON.parse(localStorage.getItem(UK) || "null"); }
            catch { return null; }
        },
        setUser: (u) => localStorage.setItem(UK, JSON.stringify(u)),
        clear: () => { localStorage.removeItem(TK); localStorage.removeItem(UK); },
        isAdmin: () => {
            const u = SRMAuth.getUser();
            return u && (u.role === "buyer" || u.role === "admin");
        },
    };
})();

/* srmFetch: wrap fetch with auth header + 401自动登出 */
window.srmFetch = async function (url, opts = {}) {
    const headers = Object.assign({}, opts.headers || {});
    const tk = SRMAuth.getToken();
    if (tk) headers["Authorization"] = "Bearer " + tk;
    if (opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
    const res = await fetch(url, Object.assign({}, opts, { headers }));
    if (res.status === 401) {
        SRMAuth.clear();
        const here = location.pathname + location.search;
        const loginPath = location.pathname.startsWith("/admin/") ? "../login.html" : "login.html";
        location.replace(loginPath + "?next=" + encodeURIComponent(here));
        throw new Error("未登录");
    }
    return res;
};

/* requireAuth: 页面顶部调用,未登录则跳login */
window.requireAuth = function (opts = {}) {
    const tk = SRMAuth.getToken();
    if (!tk) {
        const here = location.pathname + location.search;
        const loginPath = location.pathname.startsWith("/admin/") ? "../login.html" : "login.html";
        location.replace(loginPath + "?next=" + encodeURIComponent(here));
        return false;
    }
    if (opts.requireAdmin && !SRMAuth.isAdmin()) {
        alert("需要采购员权限,即将跳回首页");
        location.replace(location.pathname.startsWith("/admin/") ? "../index.html" : "index.html");
        return false;
    }
    return true;
};

/* 在navbar右上角注入登录态;需navbar存在且有.nav-cta占位 */
function initAuthNav() {
    const nav = document.querySelector(".navbar");
    if (!nav) return;
    const cta = nav.querySelector(".nav-cta");
    const user = SRMAuth.getUser();
    if (!user) return; // 未登录保持原样

    const inAdmin = location.pathname.startsWith("/admin/");
    const P = inAdmin ? "../" : "";  // 路径前缀

    // 1. 在 nav-links 注入角色快捷入口(若尚未有)
    const navLinks = nav.querySelector(".nav-links");
    if (navLinks && !navLinks.querySelector("[data-role-link]")) {
        const li = document.createElement("li");
        if (user.role === "supplier") {
            li.innerHTML = `<a href="${P}dashboard.html" data-role-link>我的工作台</a>`;
        } else {
            li.innerHTML = `<a href="${P}admin/index.html" data-role-link>采购中心</a>`;
        }
        navLinks.appendChild(li);
    }

    // 2. 右上角 CTA 换成 用户头像+下拉菜单
    if (!cta) return;

    const roleLabel = user.role === "buyer" ? "采购主管" : user.role === "admin" ? "系统管理员" : user.role === "approver" ? "审批员" : "供应商";
    const avatarChar = (user.name || user.username || "欧").charAt(0);

    // SVG 图标集 - 跟主站其它页面同一stroke风格
    const ICON = {
        home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10l9-7 9 7v10a2 2 0 01-2 2h-4v-7h-6v7H5a2 2 0 01-2-2z"/></svg>',
        dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>',
        users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>',
        bolt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
        scales: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M12 3v18M5 7l-2 6a4 4 0 008 0l-2-6M19 7l-2 6a4 4 0 008 0l-2-6M5 7l7-2 7 2"/></svg>',
        doc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>',
        external: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>',
        logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
    };

    // 菜单项按角色不同
    const menuItems = user.role === "supplier" ? [
        { icon: ICON.home, label: "我的工作台", href: P + "dashboard.html" },
        { icon: ICON.users, label: "完善企业资料", href: P + "profile.html" },
        { icon: ICON.doc, label: "采购公告", href: P + "bids.html" },
        { icon: ICON.globe, label: "平台门户", href: P + "index.html" },
        { divider: true },
        { icon: ICON.external, label: "返回官网", href: "https://hboyjd.com", external: true },
        { icon: ICON.logout, label: "退出登录", logout: true, danger: true },
    ] : [
        { icon: ICON.dashboard, label: "采购中心首页", href: P + "admin/index.html" },
        { icon: ICON.users, label: "合格供应商库", href: P + "admin/suppliers.html" },
        { icon: ICON.bolt, label: "待审核入驻", href: P + "admin/suppliers.html?status=pending" },
        { icon: ICON.scales, label: "询价单管理", href: P + "admin/inquiries.html" },
        { divider: true },
        { icon: ICON.doc, label: "采购公告", href: P + "bids.html" },
        { icon: ICON.globe, label: "平台门户", href: P + "index.html" },
        { divider: true },
        { icon: ICON.external, label: "返回官网", href: "https://hboyjd.com", external: true },
        { icon: ICON.logout, label: "退出登录", logout: true, danger: true },
    ];

    const renderMenu = () => menuItems.map(it => {
        if (it.divider) return `<div class="srm-menu-divider"></div>`;
        if (it.logout) return `<button type="button" class="srm-menu-item danger" data-srm-logout><span class="srm-menu-ic">${it.icon}</span><span>${it.label}</span></button>`;
        const target = it.external ? ' target="_blank" rel="noopener"' : '';
        return `<a class="srm-menu-item" href="${it.href}"${target}><span class="srm-menu-ic">${it.icon}</span><span>${it.label}</span></a>`;
    }).join("");

    cta.removeAttribute("href");
    cta.style.cssText = "padding:0;background:transparent;border:none;cursor:default";
    cta.innerHTML = `
      <button type="button" class="srm-user-trigger" data-srm-trigger>
          <span class="srm-user-avatar">${avatarChar}</span>
          <span class="srm-user-txt"><span class="srm-user-name">${user.name || user.username}</span><span class="srm-user-role">${roleLabel}</span></span>
          <svg class="srm-user-caret" width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M2 3.5l3 3 3-3"/></svg>
      </button>
      <div class="srm-user-menu" data-srm-menu hidden>
          <div class="srm-menu-head">
              <div class="srm-menu-avatar-lg">${avatarChar}</div>
              <div class="srm-menu-head-info">
                  <div class="srm-menu-head-name">${user.name || user.username}</div>
                  <div class="srm-menu-head-role">${roleLabel}${user.phone ? " · " + user.phone : ""}</div>
              </div>
          </div>
          <div class="srm-menu-body">${renderMenu()}</div>
      </div>
    `;

    // 注入样式(只注一次)
    if (!document.getElementById("srm-user-menu-style")) {
        const st = document.createElement("style");
        st.id = "srm-user-menu-style";
        st.textContent = `
            .nav-cta { position: relative; }
            .srm-user-trigger {
                display: inline-flex; align-items: center; gap: 10px;
                padding: 6px 12px 6px 6px;
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 999px;
                color: #fff;
                font-family: inherit;
                font-size: 13px;
                cursor: pointer;
                transition: all 0.18s;
            }
            .srm-user-trigger:hover {
                background: rgba(255,255,255,0.15);
                border-color: rgba(255,255,255,0.3);
            }
            .srm-user-trigger.is-open {
                background: rgba(37, 99, 235, 0.85);
                border-color: rgba(96, 165, 250, 0.6);
            }
            .srm-user-avatar {
                width: 28px; height: 28px;
                border-radius: 50%;
                background: linear-gradient(135deg, #2563eb, #0f2035);
                color: #fff;
                display: inline-flex; align-items: center; justify-content: center;
                font-weight: 600; font-size: 13px;
                flex-shrink: 0;
            }
            .srm-user-txt { display: inline-flex; flex-direction: column; line-height: 1.2; text-align: left; }
            .srm-user-name { font-size: 13px; font-weight: 500; }
            .srm-user-role { font-size: 10px; color: rgba(255,255,255,0.6); letter-spacing: 0.5px; }
            .srm-user-caret { opacity: 0.7; transition: transform 0.2s; }
            .srm-user-trigger.is-open .srm-user-caret { transform: rotate(180deg); opacity: 1; }

            .srm-user-menu {
                position: absolute;
                top: calc(100% + 8px);
                right: 0;
                min-width: 260px;
                background: #fff;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(10, 22, 40, 0.25);
                border: 1px solid #e2e8f0;
                overflow: hidden;
                z-index: 2000;
                animation: srmMenuIn 0.18s ease;
            }
            .srm-user-menu[hidden] { display: none; }
            @keyframes srmMenuIn {
                from { opacity: 0; transform: translateY(-6px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .srm-menu-head {
                padding: 18px 18px 16px;
                background: linear-gradient(135deg, #eff6ff, #ffffff);
                border-bottom: 1px solid #f1f5f9;
                display: flex; gap: 12px; align-items: center;
            }
            .srm-menu-avatar-lg {
                width: 44px; height: 44px;
                border-radius: 50%;
                background: linear-gradient(135deg, #2563eb, #1e293b);
                color: #fff;
                display: inline-flex; align-items: center; justify-content: center;
                font-weight: 600; font-size: 18px;
                flex-shrink: 0;
            }
            .srm-menu-head-name { font-size: 15px; font-weight: 600; color: #0a1628; margin-bottom: 3px; }
            .srm-menu-head-role { font-size: 12px; color: #64748b; }
            .srm-menu-body { padding: 6px 0; }
            .srm-menu-item {
                display: flex; align-items: center; gap: 10px;
                padding: 10px 18px;
                width: 100%;
                background: transparent;
                border: none;
                text-align: left;
                color: #334155;
                font-size: 13.5px;
                font-family: inherit;
                cursor: pointer;
                text-decoration: none;
                transition: all 0.12s;
            }
            .srm-menu-item:hover { background: #f1f5f9; color: #0a1628; }
            .srm-menu-item.danger { color: #dc2626; }
            .srm-menu-item.danger:hover { background: #fef2f2; color: #991b1b; }
            .srm-menu-ic {
                width: 18px; height: 18px;
                display: inline-flex; align-items: center; justify-content: center;
                flex-shrink: 0;
                opacity: 0.75;
                color: #64748b;
            }
            .srm-menu-ic svg { width: 16px; height: 16px; }
            .srm-menu-item:hover .srm-menu-ic { opacity: 1; color: #2563eb; }
            .srm-menu-item.danger .srm-menu-ic { color: #dc2626; opacity: 0.8; }
            .srm-menu-item.danger:hover .srm-menu-ic { color: #991b1b; opacity: 1; }
            .srm-menu-divider {
                height: 1px;
                background: #f1f5f9;
                margin: 6px 0;
            }
            @media (max-width: 640px) {
                .srm-user-txt { display: none; }
                .srm-user-trigger { padding: 4px; }
                .srm-user-menu { right: -40px; }
            }
        `;
        document.head.appendChild(st);
    }

    const trigger = cta.querySelector("[data-srm-trigger]");
    const menu = cta.querySelector("[data-srm-menu]");

    const close = () => {
        menu.hidden = true;
        trigger.classList.remove("is-open");
    };
    const toggle = () => {
        const open = menu.hidden;
        menu.hidden = !open;
        trigger.classList.toggle("is-open", open);
    };

    trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        toggle();
    });
    menu.addEventListener("click", (e) => {
        if (e.target.closest("[data-srm-logout]")) {
            e.preventDefault();
            SRMAuth.clear();
            location.href = (inAdmin ? "../" : "") + "index.html";
        }
    });
    document.addEventListener("click", (e) => {
        if (!cta.contains(e.target)) close();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") close();
    });
}

// Navbar滚动效果
function initNavbar() {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;
    const update = () => {
        if (window.scrollY > 10) navbar.classList.remove('is-flush');
        else navbar.classList.add('is-flush');
    };
    update();
    window.addEventListener('scroll', update, { passive: true });
}

// 倒计时组件
// 用法: <span class="countdown" data-deadline="2026-04-24 17:00:00"></span>
function initCountdowns() {
    const nodes = document.querySelectorAll('.countdown');
    if (!nodes.length) return;
    const fmt = n => String(n).padStart(2, '0');
    const tick = () => {
        nodes.forEach(el => {
            const t = new Date(el.dataset.deadline.replace(/-/g, '/'));
            let diff = (t - new Date()) / 1000;
            if (diff <= 0) {
                el.innerHTML = `<span class="cd-over">已截止</span>`;
                el.classList.add('is-over');
                return;
            }
            const d = Math.floor(diff / 86400); diff -= d * 86400;
            const h = Math.floor(diff / 3600); diff -= h * 3600;
            const m = Math.floor(diff / 60); diff -= m * 60;
            const s = Math.floor(diff);
            const render = el.dataset.format || 'full';
            if (render === 'compact') {
                el.innerHTML = d > 0
                    ? `<b>${d}</b><span>天</span><b>${fmt(h)}</b>:<b>${fmt(m)}</b>:<b>${fmt(s)}</b>`
                    : `<b>${fmt(h)}</b>:<b>${fmt(m)}</b>:<b>${fmt(s)}</b>`;
            } else {
                el.innerHTML = `
                    <span class="cd-block"><b>${d}</b><i>天</i></span>
                    <span class="cd-sep">·</span>
                    <span class="cd-block"><b>${fmt(h)}</b><i>时</i></span>
                    <span class="cd-sep">·</span>
                    <span class="cd-block"><b>${fmt(m)}</b><i>分</i></span>
                    <span class="cd-sep">·</span>
                    <span class="cd-block"><b>${fmt(s)}</b><i>秒</i></span>
                `;
            }
        });
    };
    tick();
    setInterval(tick, 1000);
}

// 注册向导步骤切换
function initWizard() {
    const wizard = document.querySelector('[data-wizard]');
    if (!wizard) return;
    const steps = wizard.querySelectorAll('[data-step]');
    const stamps = wizard.querySelectorAll('.step-stamp');
    let current = parseInt(wizard.dataset.current || '1', 10);
    const total = steps.length;

    const render = () => {
        steps.forEach(s => s.classList.toggle('is-active', parseInt(s.dataset.step) === current));
        stamps.forEach(st => {
            const n = parseInt(st.dataset.stampStep);
            st.classList.toggle('is-active', n === current);
            st.classList.toggle('is-done', n < current);
        });
        wizard.querySelectorAll('[data-wizard-prev]').forEach(b => b.style.visibility = current === 1 ? 'hidden' : 'visible');
        wizard.querySelectorAll('[data-wizard-next]').forEach(b => b.textContent = current === total ? '提交审核' : '下一步 →');
    };
    wizard.addEventListener('click', e => {
        if (e.target.closest('[data-wizard-next]')) {
            if (current < total) { current++; render(); }
            else {
                // 最后一步：发自定义事件,page级可拦截接真API
                const evt = new CustomEvent('wizard-submit', { cancelable: true });
                if (wizard.dispatchEvent(evt)) {
                    alert('已提交资料审核，3个工作日内您将收到短信通知。');
                }
            }
        }
        if (e.target.closest('[data-wizard-prev]')) {
            if (current > 1) { current--; render(); }
        }
        const stamp = e.target.closest('.step-stamp');
        if (stamp) {
            const n = parseInt(stamp.dataset.stampStep);
            if (n <= current) { current = n; render(); }
        }
    });
    render();
}

// 报价表合计
function initBidTable() {
    const table = document.querySelector('[data-bid-table]');
    if (!table) return;
    const totalEl = document.querySelector('[data-bid-total]');
    const recompute = () => {
        let sum = 0;
        table.querySelectorAll('tr[data-row]').forEach(row => {
            const qty = parseFloat(row.querySelector('[data-qty]').textContent) || 0;
            const price = parseFloat(row.querySelector('[data-price]').value) || 0;
            const tax = parseFloat(row.querySelector('[data-tax]').value) || 0;
            const subtotal = qty * price * (1 + tax / 100);
            row.querySelector('[data-subtotal]').textContent = subtotal.toFixed(2);
            sum += subtotal;
        });
        if (totalEl) totalEl.textContent = sum.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };
    table.addEventListener('input', recompute);
    recompute();
}

// 比价表 列hover
function initCompareTable() {
    const table = document.querySelector('[data-compare-table]');
    if (!table) return;
    table.addEventListener('mouseover', e => {
        const cell = e.target.closest('td, th');
        if (!cell) return;
        const col = cell.cellIndex;
        table.querySelectorAll('tr').forEach(tr => {
            const c = tr.cells[col];
            if (c) c.classList.add('col-hover');
        });
    });
    table.addEventListener('mouseout', () => {
        table.querySelectorAll('.col-hover').forEach(c => c.classList.remove('col-hover'));
    });
}

// 筛选器 active 切换
function initFilterPills() {
    document.querySelectorAll('[data-filter-group]').forEach(group => {
        group.addEventListener('click', e => {
            const pill = e.target.closest('[data-filter]');
            if (!pill) return;
            group.querySelectorAll('[data-filter]').forEach(p => p.classList.remove('is-active'));
            pill.classList.add('is-active');
        });
    });
}

// 文件上传预览
function initUploadCards() {
    document.querySelectorAll('.upload-card').forEach(card => {
        const input = card.querySelector('input[type="file"]');
        if (!input) return;
        input.addEventListener('change', () => {
            const f = input.files && input.files[0];
            if (!f) return;
            card.classList.add('is-uploaded');
            const nameEl = card.querySelector('.upload-filename');
            if (nameEl) nameEl.textContent = f.name + ' · ' + (f.size / 1024).toFixed(1) + ' KB';
        });
    });
}

// 排序按钮（供应商卡片）
function initSortCards() {
    const group = document.querySelector('[data-sort-group]');
    if (!group) return;
    const wrap = document.querySelector('[data-sort-target]');
    if (!wrap) return;
    const cards = [...wrap.querySelectorAll('[data-vendor]')];
    group.addEventListener('click', e => {
        const btn = e.target.closest('[data-sort-by]');
        if (!btn) return;
        group.querySelectorAll('[data-sort-by]').forEach(b => b.classList.remove('is-active'));
        btn.classList.add('is-active');
        const key = btn.dataset.sortBy;
        cards.sort((a, b) => parseFloat(a.dataset[key]) - parseFloat(b.dataset[key]));
        cards.forEach(c => wrap.appendChild(c));
    });
}

// 定标选择
function initAwardPicker() {
    const cards = document.querySelectorAll('[data-vendor]');
    cards.forEach(card => {
        card.addEventListener('click', e => {
            if (e.target.closest('a, button')) return;
            cards.forEach(c => c.classList.remove('is-selected'));
            card.classList.add('is-selected');
            const label = document.querySelector('[data-award-label]');
            if (label) label.textContent = card.querySelector('[data-vendor-name]').textContent;
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initNavbar();
    initAuthNav();
    initCountdowns();
    initWizard();
    initBidTable();
    initCompareTable();
    initFilterPills();
    initUploadCards();
    initSortCards();
    initAwardPicker();
});
