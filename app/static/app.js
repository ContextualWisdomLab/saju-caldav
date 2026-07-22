const state = { profiles: [], calendars: [], locations: [] };

const stems = [..."甲乙丙丁戊己庚辛壬癸"];
const branches = [..."子丑寅卯辰巳午未申酉戌亥"];
const elements = [..."木火土金水"];
const stemLabels = {
  "甲": "갑목 — 양의 큰나무", "乙": "을목 — 음의 풀과 덩굴",
  "丙": "병화 — 양의 큰불", "丁": "정화 — 음의 작은불",
  "戊": "무토 — 양의 큰땅", "己": "기토 — 음의 부드러운 땅",
  "庚": "경금 — 양의 단단한 쇠", "辛": "신금 — 음의 세밀한 쇠",
  "壬": "임수 — 양의 큰물", "癸": "계수 — 음의 작은물",
};
const branchLabels = {
  "子": "자수 — 쥐·물", "丑": "축토 — 소·흙", "寅": "인목 — 호랑이·나무",
  "卯": "묘목 — 토끼·나무", "辰": "진토 — 용·흙", "巳": "사화 — 뱀·불",
  "午": "오화 — 말·불", "未": "미토 — 양·흙", "申": "신금 — 원숭이·쇠",
  "酉": "유금 — 닭·쇠", "戌": "술토 — 개·흙", "亥": "해수 — 돼지·물",
};
const elementLabels = { "木": "나무", "火": "불", "土": "흙", "金": "쇠", "水": "물" };
const visibilityLabels = {
  private: "비공개",
  confidential: "제한 공개",
  public: "공개 표시",
};

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
  return `<div class="pillar">
    <span>${escapeHtml(label)}</span>
    <strong>${escapeHtml(pillar.stem_korean)} · ${escapeHtml(pillar.branch_korean)}</strong>
    <small>${escapeHtml(pillar.stem_description)}<br>${escapeHtml(pillar.branch_description)}</small>
    <details><summary>한자 표기</summary><b lang="zh-Hant">${escapeHtml(pillar.ganzhi)}</b></details>
  </div>`;
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
  $("#acceptance-note").textContent = `일주의 지지는 ${chart.day.branch_korean}, 시주의 천간은 ${chart.hour.stem_korean}입니다.`;
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
    .map((profile) => `<option value="${escapeHtml(profile.id)}">${escapeHtml(profile.name)} · ${escapeHtml(profile.birth_city_name || profile.timezone)} · 일지 ${escapeHtml(profile.chart.day.branch_korean)}, 시간 ${escapeHtml(profile.chart.hour.stem_korean)}</option>`)
    .join("");
  select.value = state.profiles.some((profile) => profile.id === selected)
    ? selected
    : state.profiles.at(-1).id;
  showChart(state.profiles.find((profile) => profile.id === select.value));
}

function renderLocations() {
  const select = $("#birth-city");
  const selected = select.value;
  select.innerHTML = [
    ...state.locations.map((location) => `<option value="${escapeHtml(location.id)}">${escapeHtml(location.label)}</option>`),
    '<option value="">목록에 없음 · 시간대 직접 지정</option>',
  ].join("");
  select.value = state.locations.some((location) => location.id === selected)
    ? selected
    : "";
  updatePlaceFields();
}

function updatePlaceFields() {
  const cityId = $("#birth-city").value;
  const city = state.locations.find((location) => location.id === cityId);
  const timezone = $("#timezone");
  const trueSolar = $("#time-mode").value === "true_solar";
  if (city) {
    timezone.value = city.timezone;
    timezone.readOnly = true;
    $("#place-note").textContent = trueSolar
      ? `${city.label}의 경도를 서버에서 자동 적용합니다. 위도와 좌표 입력은 필요하지 않습니다.`
      : `${city.label}의 시간대 ${city.timezone}를 적용합니다. 표준시는 좌표를 사용하지 않습니다.`;
    return;
  }
  timezone.readOnly = false;
  $("#place-note").textContent = trueSolar
    ? "진태양시는 경도를 자동 계산할 수 있도록 위 도시 목록에서 선택해야 합니다."
    : "IANA 시간대(예: Asia/Seoul)를 직접 입력하세요. 좌표는 필요하지 않습니다.";
}

function predicateLabel(predicate) {
  const labels = {
    "day.branch": "일주의 지지",
    "day.stem": "일주의 천간",
    "day.branch_element": "일주 지지의 오행",
    "day.stem_element": "일주 천간의 오행",
    "hour.stem": "시주의 천간",
    "hour.branch": "시주의 지지",
    "hour.stem_element": "시주 천간의 오행",
    "hour.branch_element": "시주 지지의 오행",
  };
  const value = predicate.source === "natal"
    ? `출생 ${labels[predicate.value]}`
    : optionLabel(predicate.field, predicate.value);
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
          <p class="calendar-meta">/${escapeHtml(calendar.slug)}/ · ${escapeHtml(visibilityLabels[calendar.visibility] || calendar.visibility)} · ${escapeHtml(synced)}</p>
          <p class="calendar-rule">${escapeHtml(rule)}</p>
        </div>
        <div class="calendar-actions">
          <button class="button secondary" type="button" data-action="preview">오늘부터 1년 미리보기</button>
          <button class="button primary" type="button" data-action="sync">오늘부터 1년 동기화</button>
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

function optionLabel(field, value) {
  if (field.endsWith("stem")) return `${stemLabels[value]} (${value})`;
  if (field.endsWith("branch")) return `${branchLabels[value]} (${value})`;
  return `${elementLabels[value]} (${value})`;
}

function updateValueSelect(fieldSelector, valueSelector, preferred) {
  const field = $(fieldSelector).value;
  const values = optionsForField(field);
  $(valueSelector).innerHTML = values
    .map((value) => `<option value="${value}"${value === preferred ? " selected" : ""}>${escapeHtml(optionLabel(field, value))}</option>`)
    .join("");
}

async function refresh() {
  [state.profiles, state.calendars, state.locations] = await Promise.all([
    api("/api/profiles"),
    api("/api/calendars"),
    api("/api/locations"),
  ]);
  renderLocations();
  renderProfiles();
  renderCalendars();
}

$("#time-mode").addEventListener("change", (event) => {
  updatePlaceFields();
});

$("#birth-city").addEventListener("change", updatePlaceFields);

$("#birth-calendar").addEventListener("change", (event) => {
  const lunar = event.target.value === "lunar";
  $("#leap-month-field").hidden = !lunar;
  if (!lunar) $("#leap-month-field input").checked = false;
});

$("#profile-select").addEventListener("change", (event) => {
  const profile = state.profiles.find((item) => item.id === event.target.value);
  if (profile) showChart(profile);
});

$("#day-source").addEventListener("change", (event) => {
  $("#day-value-field").hidden = event.target.value !== "literal";
});

$("#day-field").addEventListener("change", () => {
  updateValueSelect("#day-field", "#day-value");
});

$("#hour-field").addEventListener("change", () => {
  updateValueSelect("#hour-field", "#hour-value");
});

$("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = serializeForm(event.currentTarget);
  const payload = {
    ...values,
    birth_year: Number(values.birth_year),
    birth_month: Number(values.birth_month),
    birth_day: Number(values.birth_day),
    is_leap_month: event.currentTarget.elements.is_leap_month.checked,
    birth_city: values.birth_city || null,
    longitude: null,
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
    visibility: values.visibility,
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
    const result = await api(`/api/calendars/${calendarId}/${button.dataset.action}`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (button.dataset.action === "preview") {
      card.querySelector(".preview")?.remove();
      const preview = document.createElement("div");
      preview.className = "preview";
      const items = result.events.slice(0, 9)
        .map((item) => `<li>
          ${escapeHtml(new Date(item.start).toLocaleString("ko-KR"))}
          · 일지 ${escapeHtml(item.day_branch_korean)}, 시간 ${escapeHtml(item.hour_stem_korean)}
          <details><summary>한자 표기</summary><span lang="zh-Hant">${escapeHtml(item.day_pillar)} / ${escapeHtml(item.hour_pillar)}</span></details>
        </li>`)
        .join("");
      preview.innerHTML = `<strong>${result.count}개 시간을 찾았습니다.</strong><ol>${items}</ol>`;
      card.append(preview);
      notify(`오늘부터 1년 범위에서 ${result.count}개 시간을 찾았습니다.`);
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

updateValueSelect("#day-field", "#day-value", "午");
updateValueSelect("#hour-field", "#hour-value", "戊");
refresh().catch((error) => notify(`초기 데이터를 읽지 못했습니다: ${error.message}`, true));
