const state = {
  profiles: [],
  calendars: [],
  locations: [],
  compatibility: null,
};

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

function profileOption(profile, technical = false) {
  const place = profile.birth_city_name || profile.timezone;
  const knownTime = profile.birth_time_known !== false;
  const detail = technical
    ? (
      knownTime
        ? ` · 일지 ${profile.chart.day.branch_korean}, 시간 ${profile.chart.hour.stem_korean}`
        : ` · 일지 ${profile.chart.day.branch_korean}, 시각 미상`
    )
    : (knownTime ? "" : " · 시각 미상");
  return `<option value="${escapeHtml(profile.id)}">${escapeHtml(profile.name)} · ${escapeHtml(place)}${escapeHtml(detail)}</option>`;
}

function pillarMarkup(label, pillar) {
  return `<div class="pillar">
    <span>${escapeHtml(label)}</span>
    <strong>${escapeHtml(pillar.stem_korean)} · ${escapeHtml(pillar.branch_korean)}</strong>
    <small>${escapeHtml(pillar.stem_description)}<br>${escapeHtml(pillar.branch_description)}</small>
    <details><summary>한자 표기</summary><b lang="zh-Hant">${escapeHtml(pillar.ganzhi)}</b></details>
  </div>`;
}

function unknownHourPillarMarkup() {
  return `<div class="pillar unknown-pillar">
    <span>시주</span>
    <strong>미확정</strong>
    <small>태어난 시각을 몰라<br>임의로 계산하지 않습니다</small>
  </div>`;
}

function showChart(profile) {
  const chart = profile.chart;
  const knownTime = profile.birth_time_known !== false && chart.hour;
  $("#chart-profile-name").textContent = profile.name;
  $("#pillars").innerHTML = [
    pillarMarkup("년주", chart.year),
    pillarMarkup("월주", chart.month),
    pillarMarkup("일주", chart.day),
    knownTime ? pillarMarkup("시주", chart.hour) : unknownHourPillarMarkup(),
  ].join("");
  $("#acceptance-note").textContent = knownTime
    ? `일주의 지지는 ${chart.day.branch_korean}, 시주의 천간은 ${chart.hour.stem_korean}입니다.`
    : `일주의 지지는 ${chart.day.branch_korean}입니다. 태어난 시각을 몰라 시주는 계산하지 않았습니다.`;
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
  select.innerHTML = state.profiles.map((profile) => profileOption(profile, true)).join("");
  select.value = state.profiles.some((profile) => profile.id === selected)
    ? selected
    : state.profiles.at(-1).id;
  showChart(state.profiles.find((profile) => profile.id === select.value));

  document.querySelectorAll("[data-profile-choice]").forEach((choice) => {
    const previous = choice.value;
    choice.innerHTML = [
      '<option value="">새로운 사람을 입력할게요</option>',
      ...state.profiles.map((profile) => profileOption(profile)),
    ].join("");
    choice.value = state.profiles.some((profile) => profile.id === previous)
      ? previous
      : "";
    toggleNewPersonFields(choice);
  });
}

function renderLocations() {
  document.querySelectorAll("#birth-city, [data-birth-city]").forEach((select) => {
    const selected = select.value;
    select.innerHTML = [
      ...state.locations.map((location) => `<option value="${escapeHtml(location.id)}">${escapeHtml(location.label)}</option>`),
      '<option value="">목록에 없음 · 시간대 직접 지정</option>',
    ].join("");
    select.value = state.locations.some((location) => location.id === selected)
      ? selected
      : (state.locations[0]?.id || "");
  });
  updatePlaceFields();
  document.querySelectorAll("[data-person]").forEach(updatePairPlace);
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
      ? `${city.label}의 대표 경도를 서버에서 자동 적용하므로 좌표를 직접 입력할 필요가 없습니다.`
      : `${city.label}의 시간대 ${city.timezone}를 적용합니다. 표준시는 좌표를 사용하지 않습니다.`;
    return;
  }
  timezone.readOnly = false;
  $("#place-note").textContent = trueSolar
    ? "진태양시는 경도를 자동 계산할 수 있도록 위 도시 목록에서 선택해야 합니다."
    : "IANA 시간대(예: Asia/Seoul)를 직접 입력하세요. 좌표는 필요하지 않습니다.";
}

function toggleNewPersonFields(choice) {
  const prefix = choice.dataset.profileChoice;
  const fields = document.querySelector(`[data-new-profile="${prefix}"]`);
  const creating = !choice.value;
  fields.hidden = !creating;
  fields.querySelectorAll("input, select").forEach((control) => {
    control.disabled = !creating;
  });
  updateUnknownBirthTime(fields);
}

function updateUnknownBirthTime(scope) {
  const checkbox = scope.querySelector("[data-unknown-time]");
  if (!checkbox) return;
  const unknown = checkbox.checked;
  const inactive = scope.hidden;
  const timeInput = scope.querySelector("[data-time-input]");
  const timeMode = scope.querySelector("[data-time-mode]");
  const note = scope.querySelector("[data-unknown-time-note]");
  timeInput.disabled = inactive || unknown;
  timeInput.required = !unknown;
  if (timeMode) {
    if (unknown) timeMode.value = "civil";
    timeMode.disabled = inactive || unknown;
  }
  if (note) note.hidden = !unknown;
  scope.classList.toggle("birth-time-unknown", unknown);
}

function updatePairPlace(personCard) {
  const cityId = personCard.querySelector("[data-birth-city]").value;
  const city = state.locations.find((location) => location.id === cityId);
  const timezone = personCard.querySelector("[data-timezone]");
  const trueSolar = personCard.querySelector("[data-time-mode]").value === "true_solar";
  const note = personCard.querySelector("[data-place-note]");
  if (city) {
    timezone.value = city.timezone;
    timezone.readOnly = true;
    note.textContent = trueSolar
      ? `${city.label}의 대표 경도를 자동 적용하므로 좌표를 직접 입력할 필요가 없습니다.`
      : `${city.label}의 시간대 ${city.timezone}를 적용합니다.`;
    return;
  }
  timezone.readOnly = false;
  note.textContent = trueSolar
    ? "진태양시는 위 도시 목록에서 선택해야 합니다."
    : "IANA 시간대(예: Asia/Seoul)를 입력하세요. 좌표는 필요하지 않습니다.";
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
      const primary = state.profiles.find((profile) => profile.id === calendar.profile_id);
      const secondary = state.profiles.find((profile) => profile.id === calendar.secondary_profile_id);
      const rule = calendar.kind === "compatibility"
        ? `${primary?.name || "첫 번째 사람"} · ${secondary?.name || "두 번째 사람"}에게 고르게 어울리는 시간 · ${calendar.rule.include_overnight ? "24시간 전체" : "생활 시간 09–23시"}`
        : calendar.rule.predicates.map(predicateLabel).join(calendar.rule.logic === "all" ? " 그리고 " : " 또는 ");
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

function pairProfilePayload(form, prefix) {
  const values = serializeForm(form);
  const leapMonth = form.elements.namedItem(`${prefix}_is_leap_month`);
  const unknownTime = form.elements.namedItem(`${prefix}_birth_time_unknown`).checked;
  return {
    name: values[`${prefix}_name`],
    birth_calendar: values[`${prefix}_birth_calendar`],
    birth_year: Number(values[`${prefix}_birth_year`]),
    birth_month: Number(values[`${prefix}_birth_month`]),
    birth_day: Number(values[`${prefix}_birth_day`]),
    birth_time: unknownTime ? null : values[`${prefix}_birth_time`],
    birth_time_known: !unknownTime,
    is_leap_month: leapMonth.checked,
    birth_city: values[`${prefix}_birth_city`] || null,
    gender: values[`${prefix}_gender`],
    timezone: values[`${prefix}_timezone`],
    time_mode: unknownTime ? "civil" : values[`${prefix}_time_mode`],
    longitude: null,
  };
}

async function resolvePairProfile(form, prefix) {
  const profileId = form.elements.namedItem(`${prefix}_profile_id`).value;
  if (profileId) {
    const profile = state.profiles.find((item) => item.id === profileId);
    if (!profile) throw new Error("선택한 사람을 다시 불러오지 못했습니다.");
    return profile;
  }
  return api("/api/profiles", {
    method: "POST",
    body: JSON.stringify(pairProfilePayload(form, prefix)),
  });
}

function renderCompatibility(result, primary, secondary) {
  state.compatibility = { result, primary, secondary };
  $("#pair-names").textContent = `${primary.name} · ${secondary.name}`;
  $("#pair-result-count").textContent = `${result.count}개의 가까운 후보를 찾았습니다.`;
  $("#pair-timezone").textContent = `첫 번째 사람의 ${primary.timezone} 기준 · ${result.include_overnight ? "24시간 전체" : "생활 시간 09–23시"}`;
  const list = $("#compatibility-list");
  if (!result.events.length) {
    list.innerHTML = result.include_overnight
      ? '<li class="empty-state">1년 안에서 추천 기준을 만족하는 시간을 찾지 못했습니다.</li>'
      : '<li class="empty-state">생활 시간 안에서 후보를 찾지 못했습니다. 24시간 전체로 다시 찾아보세요.</li>';
  } else {
    list.innerHTML = result.events.map((item) => {
      const start = new Date(item.start);
      const end = new Date(item.end);
      const day = start.toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "long",
        day: "numeric",
        weekday: "short",
        timeZone: primary.timezone,
      });
      const timeOptions = {
        hour: "numeric",
        minute: "2-digit",
        timeZone: primary.timezone,
      };
      const timeRange = `${start.toLocaleTimeString("ko-KR", timeOptions)}–${end.toLocaleTimeString("ko-KR", timeOptions)}`;
      const reasons = item.reasons.slice(0, 3)
        .map((reason) => `<li>${escapeHtml(reason)}</li>`)
        .join("");
      return `<li class="compatibility-card">
        <div class="candidate-when">
          <time datetime="${escapeHtml(item.start)}">${escapeHtml(day)}</time>
          <strong>${escapeHtml(timeRange)}</strong>
        </div>
        <div class="score-badge" aria-label="조화 점수 ${escapeHtml(item.score)}점">
          <b>${escapeHtml(item.score)}</b><span>조화 점수</span>
        </div>
        <div class="candidate-copy">
          <h3>${escapeHtml(item.label)}</h3>
          <ul>${reasons}</ul>
          <details>
            <summary>사주 표기 보기</summary>
            <span>일지 ${escapeHtml(item.day_branch_korean)} · 시간 ${escapeHtml(item.hour_branch_korean)}</span>
            <small lang="zh-Hant">${escapeHtml(item.day_pillar)} / ${escapeHtml(item.hour_pillar)}</small>
          </details>
        </div>
      </li>`;
    }).join("");
  }
  const calendarForm = document.getElementById("compatibility-calendar-form");
  calendarForm.elements.namedItem("primary_profile_id").value = primary.id;
  calendarForm.elements.namedItem("secondary_profile_id").value = secondary.id;
  calendarForm.elements.namedItem("name").value = "둘이 좋은 시간";
  $("#compatibility-result").hidden = false;
  $("#compatibility-result").scrollIntoView({ behavior: "smooth", block: "start" });
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

$("#pair-form").addEventListener("change", (event) => {
  const choice = event.target.closest("[data-profile-choice]");
  if (choice) {
    toggleNewPersonFields(choice);
    return;
  }
  const personCard = event.target.closest("[data-person]");
  if (!personCard) return;
  if (event.target.matches("[data-unknown-time]")) {
    updateUnknownBirthTime(personCard.querySelector("[data-new-profile]"));
    updatePairPlace(personCard);
    return;
  }
  if (event.target.matches("[data-calendar-kind]")) {
    const lunar = event.target.value === "lunar";
    const leap = personCard.querySelector("[data-leap-month]");
    leap.hidden = !lunar;
    if (!lunar) leap.querySelector("input").checked = false;
  }
  if (event.target.matches("[data-birth-city], [data-time-mode]")) {
    updatePairPlace(personCard);
  }
});

$("#birth-calendar").addEventListener("change", (event) => {
  const lunar = event.target.value === "lunar";
  $("#leap-month-field").hidden = !lunar;
  if (!lunar) $("#leap-month-field input").checked = false;
});

$("#profile-form [data-unknown-time]").addEventListener("change", (event) => {
  updateUnknownBirthTime(event.currentTarget.closest("form"));
  updatePlaceFields();
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
  const unknownTime = event.currentTarget.elements.namedItem("birth_time_unknown").checked;
  const payload = {
    ...values,
    birth_time: unknownTime ? null : values.birth_time,
    birth_time_known: !unknownTime,
    birth_year: Number(values.birth_year),
    birth_month: Number(values.birth_month),
    birth_day: Number(values.birth_day),
    is_leap_month: event.currentTarget.elements.namedItem("is_leap_month").checked,
    birth_city: values.birth_city || null,
    time_mode: unknownTime ? "civil" : values.time_mode,
    longitude: null,
  };
  delete payload.birth_time_unknown;
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

$("#pair-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = "두 사람의 시간을 계산하고 있습니다…";
  try {
    const primary = await resolvePairProfile(form, "primary");
    const secondary = await resolvePairProfile(form, "secondary");
    if (primary.id === secondary.id) {
      throw new Error("서로 다른 두 사람을 선택하세요.");
    }
    const result = await api("/api/compatibility/preview", {
      method: "POST",
      body: JSON.stringify({
        primary_profile_id: primary.id,
        secondary_profile_id: secondary.id,
        limit: 12,
        include_overnight: form.elements.namedItem("include_overnight").value === "true",
      }),
    });
    await refresh();
    const primaryChoice = $('[data-profile-choice="primary"]');
    const secondaryChoice = $('[data-profile-choice="secondary"]');
    primaryChoice.value = primary.id;
    secondaryChoice.value = secondary.id;
    toggleNewPersonFields(primaryChoice);
    toggleNewPersonFields(secondaryChoice);
    renderCompatibility(result, primary, secondary);
    notify(`${primary.name} · ${secondary.name}의 가까운 좋은 시간을 찾았습니다.`);
  } catch (error) {
    notify(`좋은 시간을 찾지 못했습니다: ${error.message}`, true);
  } finally {
    button.disabled = false;
    button.textContent = "둘이 좋은 날과 시간 찾기";
  }
});

$("#compatibility-calendar-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = serializeForm(event.currentTarget);
  const button = event.currentTarget.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const calendar = await api("/api/compatibility/calendars", {
      method: "POST",
      body: JSON.stringify({
        ...values,
        limit: 36,
        include_overnight: state.compatibility.result.include_overnight,
      }),
    });
    await refresh();
    notify(`‘${calendar.name}’ 캘린더를 저장했습니다. 아래에서 동기화할 수 있습니다.`);
    $(".library").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    notify(`캘린더를 저장하지 못했습니다: ${error.message}`, true);
  } finally {
    button.disabled = false;
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
      const primary = state.profiles.find((profile) => profile.id === calendar.profile_id);
      const displayOptions = primary ? { timeZone: primary.timezone } : {};
      const items = result.events.slice(0, 9)
        .map((item) => `<li>
          ${escapeHtml(new Date(item.start).toLocaleString("ko-KR", displayOptions))}
          ${item.score
            ? `· 조화 점수 ${escapeHtml(item.score)}점 · ${escapeHtml(item.label)}`
            : `· 일지 ${escapeHtml(item.day_branch_korean)}, 시간 ${escapeHtml(item.hour_stem_korean)}`}
          <details><summary>사주 표기</summary><span lang="zh-Hant">${escapeHtml(item.day_pillar)} / ${escapeHtml(item.hour_pillar)}</span></details>
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
updateUnknownBirthTime($("#profile-form"));
document.querySelectorAll("[data-new-profile]").forEach(updateUnknownBirthTime);
refresh().catch((error) => notify(`초기 데이터를 읽지 못했습니다: ${error.message}`, true));
