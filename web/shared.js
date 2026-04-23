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

    if (user) {
        // 1. 在 nav-links 注入角色快捷入口(若尚未有)
        const navLinks = nav.querySelector(".nav-links");
        const inAdmin = location.pathname.startsWith("/admin/");
        if (navLinks && !navLinks.querySelector("[data-role-link]")) {
            const li = document.createElement("li");
            if (user.role === "supplier") {
                const href = inAdmin ? "../dashboard.html" : "dashboard.html";
                li.innerHTML = `<a href="${href}" data-role-link>我的工作台</a>`;
            } else {
                // buyer / admin / approver
                const href = inAdmin ? "index.html" : "admin/index.html";
                li.innerHTML = `<a href="${href}" data-role-link>采购中心</a>`;
            }
            navLinks.appendChild(li);
        }

        // 2. 右上角 cta 换成 用户名+退出
        if (cta) {
            const roleLabel = user.role === "buyer" ? "采购" : user.role === "admin" ? "管理" : user.role === "approver" ? "审批" : "供应商";
            cta.innerHTML = `<span style="display:inline-flex;align-items:center;gap:10px"><span>${user.name || user.username}</span><span style="font-size:11px;opacity:.6">${roleLabel}</span><span data-srm-logout style="margin-left:6px;padding:2px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.25);font-size:11px;cursor:pointer">退出</span></span>`;
            cta.removeAttribute("href");
            cta.style.cursor = "default";
            cta.addEventListener("click", (e) => {
                if (e.target.closest("[data-srm-logout]")) {
                    e.preventDefault();
                    SRMAuth.clear();
                    location.href = inAdmin ? "../index.html" : "index.html";
                }
            });
        }
    }
    // 未登录保持原状(index.html的"供应商入驻"CTA)
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
