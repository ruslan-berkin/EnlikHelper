const equipmentGrid = document.querySelector("#equipment-grid");
const alertsList = document.querySelector("#alerts-list");
const equipmentCount = document.querySelector("#equipment-count");
const alertsCount = document.querySelector("#alerts-count");
const uploadForm = document.querySelector("#upload-form");
const uploadMessage = document.querySelector("#upload-message");
const refreshButton = document.querySelector("#refresh-button");
const aiReportButton = document.querySelector("#ai-report-button");
const aiReportContainer = document.querySelector("#ai-report");
const ticketsList = document.querySelector("#tickets-list");
const ticketsCount = document.querySelector("#tickets-count");
const manualEquipment = document.querySelector("#manual-equipment");
const manualUploadForm = document.querySelector("#manual-upload-form");
const manualUploadMessage = document.querySelector("#manual-upload-message");
const manualSearchForm = document.querySelector("#manual-search-form");
const manualsList = document.querySelector("#manuals-list");
const manualResults = document.querySelector("#manual-results");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);
}

function renderAiReport(report) {
  const statusLabels = {
    normal: "Норма",
    attention: "Требует внимания",
  };

  const equipmentHtml = report.equipment.map((item) => `
    <article class="ai-equipment">
      <h3>
        ${escapeHtml(item.equipment_id)}
        <span class="status-badge ${escapeHtml(item.status)}">
          ${escapeHtml(statusLabels[item.status] || item.status)}
        </span>
      </h3>

      <h4>Наблюдения</h4>
      <ul>
        ${item.observations.map((text) => `
          <li>${escapeHtml(text)}</li>
        `).join("")}
      </ul>

      <h4>Рекомендуемые проверки</h4>
      <ul>
        ${item.recommended_checks.map((text) => `
          <li>${escapeHtml(text)}</li>
        `).join("")}
      </ul>
    </article>
  `).join("");

  const limitationsHtml = report.limitations.map((text) => `
    <li>${escapeHtml(text)}</li>
  `).join("");

  aiReportContainer.innerHTML = `
    <p class="ai-summary">${escapeHtml(report.summary)}</p>

    ${equipmentHtml}

    <div class="limitations">
      <strong>Ограничения отчёта</strong>
      <ul>${limitationsHtml}</ul>
    </div>
  `;
}

function renderEquipment(items) {
  if (items.length === 0) {
    equipmentGrid.innerHTML =
      '<div class="empty">В базе пока нет оборудования.</div>';
    return;
  }

  equipmentGrid.innerHTML = items.map((item) => `
    <article class="equipment-card">
      <h3>${escapeHtml(item.equipment_id)}</h3>

      <div class="metrics">
        <div class="metric">
          <span>Измерений</span>
          <strong>${item.readings_count}</strong>
        </div>

        <div class="metric">
          <span>Средняя температура</span>
          <strong>${item.avg_temperature.toFixed(1)} °C</strong>
        </div>

        <div class="metric">
          <span>Макс. температура</span>
          <strong>${item.max_temperature.toFixed(1)} °C</strong>
        </div>

        <div class="metric">
          <span>Макс. вибрация</span>
          <strong>${item.max_vibration.toFixed(1)} мм/с</strong>
        </div>
      </div>
    </article>
  `).join("");
}

function renderAlerts(items) {
  if (items.length === 0) {
    alertsList.innerHTML =
      '<div class="empty">Превышений порогов не обнаружено.</div>';
    return;
  }

  alertsList.innerHTML = items.map((alert) => `
    <article class="alert">
      <strong>
        ${escapeHtml(alert.equipment_id)}
        ·
        ${escapeHtml(alert.timestamp)}
      </strong>

      <p>${alert.reasons.map(escapeHtml).join(", ")}</p>
    </article>
  `).join("");
}

function renderTickets(items) {
  if (items.length === 0) {
    ticketsList.innerHTML =
      '<div class="empty">Заявок пока нет.</div>';
    return;
  }

  const statusLabels = {
    draft: "Черновик",
    approved: "Одобрена",
    closed: "Закрыта",
    cancelled: "Отменена",
  };

  const priorityLabels = {
    medium: "Средний",
    high: "Высокий",
  };

  ticketsList.innerHTML = items.map((ticket) => `
    <article class="ticket">
      <div class="ticket-heading">
        <div>
          <span class="ticket-number">
            Заявка №${ticket.ticket_id}
          </span>
          <h3>${escapeHtml(ticket.title)}</h3>
        </div>

        <span class="ticket-status ${escapeHtml(ticket.status)}">
          ${escapeHtml(statusLabels[ticket.status] || ticket.status)}
        </span>
      </div>

      <p>${escapeHtml(ticket.description)}</p>

      <div class="ticket-meta">
        <span>
          Оборудование:
          <strong>${escapeHtml(ticket.equipment_id)}</strong>
        </span>

        <span>
          Приоритет:
          <strong>
            ${escapeHtml(
    priorityLabels[ticket.priority] || ticket.priority
  )}
          </strong>
        </span>

        <span>
          Источник:
          <strong>
            ${escapeHtml(ticket.source_alert_timestamp)}
          </strong>
        </span>
      </div>
    </article>
  `).join("");
}

function renderManuals(items) {
  if (items.length === 0) {
    manualsList.innerHTML =
      '<div class="empty">Для этого оборудования пока нет инструкций.</div>';
    return;
  }

  manualsList.innerHTML = items.map((document) => `
    <article class="manual-document">
      <strong>${escapeHtml(document.filename)}</strong>
      <span>${document.page_count} стр. · ${document.chunks_count} фрагм.</span>
    </article>
  `).join("");
}

function renderManualMatches(matches) {
  if (matches.length === 0) {
    manualResults.innerHTML =
      '<div class="empty">Подходящих фрагментов не найдено.</div>';
    return;
  }

  manualResults.innerHTML = matches.map((match) => `
    <article class="manual-match">
      <div class="manual-citation">${escapeHtml(match.citation)}</div>
      <p>${escapeHtml(match.content)}</p>
      <span>Сходство: ${Math.round(match.score * 100)}%</span>
    </article>
  `).join("");
}

async function loadManuals() {
  const equipmentId = manualEquipment.value;

  if (!equipmentId) {
    renderManuals([]);
    return;
  }

  try {
    const response = await fetch(
      `/api/manuals?equipment_id=${encodeURIComponent(equipmentId)}`
    );
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "Не удалось загрузить инструкции");
    }

    renderManuals(result.documents);
  } catch (error) {
    manualsList.innerHTML =
      `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

async function loadReport() {
  refreshButton.disabled = true;

  try {
    const response = await fetch("/api/report");

    if (!response.ok) {
      throw new Error("Не удалось загрузить отчёт");
    }

    const report = await response.json();

    equipmentCount.textContent = report.equipment_count;
    alertsCount.textContent = report.alerts_count;
    ticketsCount.textContent = report.tickets_count;

    renderEquipment(report.equipment);
    renderAlerts(report.alerts);
    renderTickets(report.tickets);

    const previousEquipment = manualEquipment.value;
    manualEquipment.innerHTML = report.equipment.map((item) => `
      <option value="${escapeHtml(item.equipment_id)}">
        ${escapeHtml(item.equipment_id)}
      </option>
    `).join("");

    if (report.equipment.some(
      (item) => item.equipment_id === previousEquipment
    )) {
      manualEquipment.value = previousEquipment;
    }

    await loadManuals();
  } catch (error) {
    equipmentGrid.innerHTML =
      `<div class="empty">${escapeHtml(error.message)}</div>`;
  } finally {
    refreshButton.disabled = false;
  }
}

aiReportButton.addEventListener("click", async () => {
  aiReportButton.disabled = true;
  aiReportButton.textContent = "Формируем отчёт…";

  aiReportContainer.innerHTML = `
    <div class="empty">
      Анализируем рассчитанные показатели и предупреждения…
    </div>
  `;

  try {
    const response = await fetch("/api/ai-report", {
      method: "POST",
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(
        result.detail || "Не удалось сформировать AI-отчёт"
      );
    }

    renderAiReport(result);
  } catch (error) {
    aiReportContainer.innerHTML = `
      <div class="empty">
        ${escapeHtml(error.message)}
      </div>
    `;
  } finally {
    aiReportButton.disabled = false;
    aiReportButton.textContent = "Сформировать AI-отчёт";
  }
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const fileInput = document.querySelector("#csv-file");
  const file = fileInput.files[0];

  if (!file) {
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  const submitButton = uploadForm.querySelector("button");
  submitButton.disabled = true;
  uploadMessage.className = "message";
  uploadMessage.textContent = "Загрузка…";

  try {
    const response = await fetch("/api/readings/import", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "Ошибка загрузки");
    }

    uploadMessage.className = "message success";
    uploadMessage.textContent =
      `Файл обработан. Добавлено новых измерений: ${result.inserted_count}.`;

    uploadForm.reset();
    await loadReport();
  } catch (error) {
    uploadMessage.className = "message error";
    uploadMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

manualEquipment.addEventListener("change", async () => {
  manualResults.innerHTML =
    '<div class="empty">Задайте вопрос по инструкции.</div>';
  await loadManuals();
});

manualUploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = document.querySelector("#manual-file").files[0];
  const equipmentId = manualEquipment.value;

  if (!file || !equipmentId) {
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  const submitButton = manualUploadForm.querySelector("button");
  submitButton.disabled = true;
  manualUploadMessage.className = "message";
  manualUploadMessage.textContent = "Извлекаем текст и создаём индекс…";

  try {
    const response = await fetch(
      `/api/manuals/${encodeURIComponent(equipmentId)}/import`,
      { method: "POST", body: formData }
    );
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "Не удалось добавить инструкцию");
    }

    manualUploadMessage.className = "message success";
    manualUploadMessage.textContent = result.created
      ? `Добавлено: ${result.document.filename}.`
      : "Эта инструкция уже была загружена.";
    manualUploadForm.reset();
    await loadManuals();
  } catch (error) {
    manualUploadMessage.className = "message error";
    manualUploadMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

manualSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = document.querySelector("#manual-query").value.trim();
  const equipmentId = manualEquipment.value;

  if (!query || !equipmentId) {
    return;
  }

  const submitButton = manualSearchForm.querySelector("button");
  submitButton.disabled = true;
  manualResults.innerHTML =
    '<div class="empty">Ищем подходящие страницы…</div>';

  try {
    const response = await fetch(
      `/api/manuals/${encodeURIComponent(equipmentId)}/search`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      }
    );
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "Не удалось выполнить поиск");
    }

    renderManualMatches(result.matches);
  } catch (error) {
    manualResults.innerHTML =
      `<div class="empty">${escapeHtml(error.message)}</div>`;
  } finally {
    submitButton.disabled = false;
  }
});

refreshButton.addEventListener("click", loadReport);

loadReport();
