const state = { profiles: [], calendars: [] };

const stems = [..."甲乙丙丁戊己庚辛壬癸"];
const branches = [..."子丑寅卯辰巳午未申酉戌亥"];
const elements = [..."木火土金水"];

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[character],
  );
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (_) {
      // Keep the HTTP status if the server did not return JSON.
    }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function notify(message, error = false) {
  const notice = $("#notice");
  notice.textContent = message;
  notice.classList.toggle("error", error);
  notice.classList.add("visible");
  window.clearTimeout(notify.timer);
  notify.timer = window.setTimeout(() => notice.classList.remove("visible"), 4200);
}

function serializeForm(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function pillarMarkup(label, pillar) {
  return `<div class="pillar"><span>${escapeHtml(label)}</span><strong>${escapeHtml(pillar.ganzhi)}</strong><small>${escapeHtml(pillar.stem_element)} · ${escapeHtml(pillar.branch_element)}</small></div>`;
}

function showChart(profile) {
  const chart = profile.chart;
  $("#chart-profile-name").textContent = profile.name;
  $("#pillars").innerHTML = [
    pillarMarkup("년주", chart.year),
    pillarMarkup("월주", chart.month),
    pillarMarkup("일주", chart.day),
    pillarMarkup("시주", chart.hour),
  ].join("");
  $("#acceptance-note").textContent = `일지 ${chart.day.branch}${chart.day.branch_element} · 시간 ${chart.hour.stem}${chart.hour.stem_element}`;
  $("#chart-result").hidden = false;
}

function renderProfiles() {
  const select = $("#profile-select");
  const selected = select.value;
  if (!state.profiles.length) {
    select.innerHTML = '<option value="">먼저 출생 프로필을 저장하세요</option>';
    $("#chart-result").hidden = true;
    return;
  }
  select.innerHTML = state.profiles
    .map((profile) => `<option value="${escapeHtml(profile.id)}">${escapeHtml(profile.name)} · ${escapeHtml(profile.chart.day.ganzhi)}일 ${escapeHtml(profile.chart.hour.ganzhi)}시</option>`)
    .join("");
  select.value = state.profiles.some((profile) => profile.id === selected)
    ? selected
    : state.profiles.at(-1).id;
  showChart(state.profiles.find((profile) => profile.id === select.value));
}

function predicateLabel(predicate) {
  const labels = {
    "day.branch": "일지",
    "day.stem": "일간",
    "day.branch_element": "일지 오행",
    "day.stem_element": "일간 오행",
    "hour.stem": "시간",
    "hour.branch": "시지",
    "hour.stem_element": "시간 오행",
    "hour.branch_element": "시지 오행",
  };
  const value = predicate.source === "natal" ? `출생 ${labels[predicate.value]}` : predicate.value;
  return `${labels[predicate.field]} = ${value}`;
}

function renderCalendars() {
  const list = $("#calendar-list");
  if (!state.calendars.length) {
    list.innerHTML = '<p class="empty-state">아직 만든 캘린더가 없습니다.</p>';
    return;
  }
  list.innerHTML = state.calendars
    .map((calendar) => {
      const rule = calendar.rule.predicates.map(predicateLabel).join(calendar.rule.logic === "all" ? " 그리고 " : " 또는 ");
      const synced = calendar.last_synced_at ? new Date(calendar.last_synced_at).toLocaleString("ko-KR") : "아직 동기화하지 않음";
      return `<article class="calendar-card" data-calendar-id="${escapeHtml(calendar.id)}">
        <div>
          <h3>${escapeHtml(calendar.name)}</h3>
          <p class="calendar-meta">/${escapeHtml(calendar.slug)}/ · ${escapeHtml(synced)}</p>
          <p class="calendar-rule">${escapeHtml(rule)}</p>
        </div>
        <div class="calendar-actions">
          <button class="button secondary" type="button" data-action="preview">90일 미리보기</button>
          <button class="button primary" type="button" data-action="sync">18개월 동기화</button>
          <button class="button danger" type="button" data-action="delete">삭제</button>
        </div>
      </article>`;
    })
    .join("");
}

function optionsForField(field) {
  if (field.endsWith("stem")) return stems;
  if (field.endsWith("branch")) return branches;
  return elements;
}

function updateValueSelect(fieldSelector, valueSelector, preferred) {
  const field = $(fieldSelector).value;
  const values = optionsForField(field);
  $(valueSelector).innerHTML = values
    .map((value) => `<option value="${value}"${value === preferred ? " selected" : ""}>${value}</option>`)
    .join("");
}

function dateRange(months) {
  const start = new Date();
  const end = new Date(start);
  end.setMonth(end.getMonth() + months);
  const iso = (value) => value.toISOString().slice(0, 10);
  return { start_date: iso(start), end_date: iso(end) };
}

async function refresh() {
  [state.profiles, state.calendars] = await Promise.all([
    api("/api/profiles"),
    api("/api/calendars"),
  ]);
  renderProfiles();
  renderCalendars();
}

$("#time-mode").addEventListener("change", (event) => {
  $("#longitude-field").hidden = event.target.value !== "true_solar";
});

$("#profile-select").addEventListener("change", (event) => {
  const profile = state.profiles.find((item) => item.id === event.target.value);
  if (profile) showChart(profile);
});

$("#day-source").addEventListener("change", (event) => {
  $("#day-value-field").hidden = event.target.value !== "literal";
});

$("#day-field").addEventListener("change", () => {
  updateValueSelect("#day-field", "#day-value", "亥");
});

$("#hour-field").addEventListener("change", () => {
  updateValueSelect("#hour-field", "#hour-value", "壬");
});

$("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = serializeForm(event.currentTarget);
  const payload = {
    ...values,
    longitude: values.time_mode === "true_solar" ? Number(values.longitude) : null,
  };
  try {
    const profile = await api("/api/profiles", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await refresh();
    $("#profile-select").value = profile.id;
    showChart(profile);
    notify(`‘${profile.name}’ 명식을 저장했습니다.`);
  } catch (error) {
    notify(`명식을 저장하지 못했습니다: ${error.message}`, true);
  }
});

$("#calendar-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = serializeForm(event.currentTarget);
  const dayPredicate = values.day_source === "natal"
    ? { field: values.day_field, source: "natal", value: values.day_field }
    : { field: values.day_field, source: "literal", value: values.day_value };
  const payload = {
    profile_id: values.profile_id,
    name: values.name,
    slug: values.slug,
    rule: {
      logic: values.logic,
      predicates: [
        dayPredicate,
        { field: values.hour_field, source: "literal", value: values.hour_value },
      ],
    },
  };
  try {
    await api("/api/calendars", { method: "POST", body: JSON.stringify(payload) });
    await refresh();
    notify(`‘${values.name}’ 캘린더를 만들었습니다.`);
  } catch (error) {
    notify(`캘린더를 만들지 못했습니다: ${error.message}`, true);
  }
});

$("#calendar-list").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const card = button.closest("[data-calendar-id]");
  const calendarId = card.dataset.calendarId;
  const calendar = state.calendars.find((item) => item.id === calendarId);
  button.disabled = true;
  try {
    if (button.dataset.action === "delete") {
      await api(`/api/calendars/${calendarId}`, { method: "DELETE" });
      await refresh();
      notify(`‘${calendar.name}’ 캘린더를 삭제했습니다.`);
      return;
    }
    const months = button.dataset.action === "preview" ? 3 : 18;
    const result = await api(`/api/calendars/${calendarId}/${button.dataset.action}`, {
      method: "POST",
      body: JSON.stringify(dateRange(months)),
    });
    if (button.dataset.action === "preview") {
      card.querySelector(".preview")?.remove();
      const preview = document.createElement("div");
      preview.className = "preview";
      const items = result.events.slice(0, 9)
        .map((item) => `<li>${escapeHtml(new Date(item.start).toLocaleString("ko-KR"))} · ${escapeHtml(item.day_pillar)}/${escapeHtml(item.hour_pillar)}</li>`)
        .join("");
      preview.innerHTML = `<strong>${result.count}개 시간을 찾았습니다.</strong><ol>${items}</ol>`;
      card.append(preview);
      notify(`90일 범위에서 ${result.count}개 시간을 찾았습니다.`);
    } else {
      await refresh();
      notify(`${result.event_count}개 이벤트를 CalDAV에 동기화했습니다.`);
    }
  } catch (error) {
    notify(`작업을 완료하지 못했습니다: ${error.message}`, true);
  } finally {
    button.disabled = false;
  }
});

updateValueSelect("#day-field", "#day-value", "亥");
updateValueSelect("#hour-field", "#hour-value", "壬");
refresh().catch((error) => notify(`초기 데이터를 읽지 못했습니다: ${error.message}`, true));
