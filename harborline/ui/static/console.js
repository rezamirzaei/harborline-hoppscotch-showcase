(function () {
  const STORAGE = {
    graphqlQuery: "harborline.graphql.query",
    graphqlVariables: "harborline.graphql.variables",
  };

  const tryParseJson = (value) => {
    try {
      return { ok: true, value: JSON.parse(value) };
    } catch (err) {
      return { ok: false, error: err };
    }
  };

  const formatJson = (value) => {
    const parsed = tryParseJson(value);
    if (!parsed.ok) return value;
    return JSON.stringify(parsed.value, null, 2);
  };

  const createAppender = (logEl, { maxLines = 250 } = {}) => {
    const lines = [];

    const render = () => {
      logEl.textContent = `${lines.join("\n")}\n`;
      logEl.scrollTop = logEl.scrollHeight;
    };

    const append = (message) => {
      lines.push(message);
      while (lines.length > maxLines) {
        lines.shift();
      }
      render();
    };

    const clear = () => {
      lines.length = 0;
      logEl.textContent = "";
    };

    return { append, clear };
  };

  const fetchGraphql = async ({ query, variables }) => {
    const response = await fetch("/graphql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, variables }),
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch (err) {
      payload = { errors: [{ message: "Response was not valid JSON." }] };
    }
    return { status: response.status, ok: response.ok, payload };
  };

  const fetchJson = async (url, options = {}) => {
    const response = await fetch(url, options);
    let payload = null;
    try {
      payload = await response.json();
    } catch (err) {
      payload = { detail: "Response was not valid JSON." };
    }
    return { status: response.status, ok: response.ok, payload };
  };

  const renderGraphqlToPre = (output, result) => {
    const header = `HTTP ${result.status}`;
    output.textContent = `${header}\n${JSON.stringify(result.payload, null, 2)}`;
  };

  const graphqlSection = document.querySelector("[data-graphql]");
  if (graphqlSection) {
    const queryInput = document.getElementById("graphql-query");
    const variablesInput = document.getElementById("graphql-variables");
    const runButton = document.getElementById("graphql-run");
    const clearButton = document.getElementById("graphql-clear");
    const output = document.getElementById("graphql-output");

    const savedQuery = window.localStorage.getItem(STORAGE.graphqlQuery);
    const savedVariables = window.localStorage.getItem(STORAGE.graphqlVariables);
    if (savedQuery) queryInput.value = savedQuery;
    if (savedVariables) variablesInput.value = savedVariables;

    const runQuery = async () => {
      runButton.disabled = true;
      let variables = {};
      try {
        variables = variablesInput.value ? JSON.parse(variablesInput.value) : {};
      } catch (err) {
        output.textContent = "Variables JSON is invalid.";
        runButton.disabled = false;
        return;
      }
      window.localStorage.setItem(STORAGE.graphqlQuery, queryInput.value);
      window.localStorage.setItem(STORAGE.graphqlVariables, formatJson(variablesInput.value || "{}"));
      output.textContent = "Running...";
      try {
        const result = await fetchGraphql({ query: queryInput.value, variables });
        renderGraphqlToPre(output, result);
      } catch (err) {
        output.textContent = "GraphQL request failed.";
      } finally {
        runButton.disabled = false;
      }
    };

    runButton?.addEventListener("click", runQuery);
    queryInput?.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") runQuery();
    });
    variablesInput?.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") runQuery();
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "f") {
        variablesInput.value = formatJson(variablesInput.value || "{}");
      }
    });
    clearButton?.addEventListener("click", () => {
      output.textContent = "";
    });
  }

  const graphCustomerSection = document.querySelector("[data-graph-customer]");
  if (graphCustomerSection) {
    const queryInput = document.getElementById("reco-query");
    const customerInput = document.getElementById("reco-customer-id");
    const limitInput = document.getElementById("reco-limit");
    const runButton = document.getElementById("reco-run");
    const clearButton = document.getElementById("reco-clear");
    const meta = document.getElementById("reco-meta");
    const table = document.getElementById("reco-table");
    const output = document.getElementById("reco-output");

    const renderRecommendations = (result) => {
      output.textContent = JSON.stringify(result.payload, null, 2);
      table.replaceChildren();
      const data = result.payload?.data?.recommendations;
      if (!data) {
        meta.textContent = "No recommendation data returned.";
        return;
      }
      meta.textContent = `source=${data.source} · generatedAt=${data.generatedAt}`;

      const header = document.createElement("div");
      header.className = "table-row table-header";
      header.innerHTML = "<div>SKU</div><div>Score</div><div>Evidence</div>";
      table.appendChild(header);

      if (!data.items?.length) {
        const empty = document.createElement("div");
        empty.className = "table-row empty";
        empty.textContent = "No recommendations yet.";
        table.appendChild(empty);
        return;
      }

      data.items.forEach((item) => {
        const row = document.createElement("div");
        row.className = "table-row";

        const sku = document.createElement("div");
        sku.textContent = item.sku;

        const score = document.createElement("div");
        score.textContent = String(item.score);

        const evidence = document.createElement("div");
        evidence.textContent = (item.evidence || []).join(", ");

        row.appendChild(sku);
        row.appendChild(score);
        row.appendChild(evidence);
        table.appendChild(row);
      });
    };

    const run = async () => {
      const customerId = customerInput?.value?.trim();
      const limit = parseInt(limitInput?.value || "10", 10);
      if (!customerId) {
        meta.textContent = "Customer ID is required.";
        return;
      }
      runButton.disabled = true;
      meta.textContent = "Running...";
      try {
        const result = await fetchGraphql({
          query: queryInput?.value || "",
          variables: { customerId, limit },
        });
        renderRecommendations(result);
      } catch (err) {
        meta.textContent = "GraphQL request failed.";
      } finally {
        runButton.disabled = false;
      }
    };

    runButton?.addEventListener("click", run);
    clearButton?.addEventListener("click", () => {
      meta.textContent = "";
      table.replaceChildren();
      output.textContent = "";
    });

    if (customerInput?.value?.trim()) {
      run();
    }
  }

  const graphSkuSection = document.querySelector("[data-graph-sku]");
  if (graphSkuSection) {
    const queryInput = document.getElementById("also-query");
    const skuInput = document.getElementById("also-sku");
    const limitInput = document.getElementById("also-limit");
    const runButton = document.getElementById("also-run");
    const clearButton = document.getElementById("also-clear");
    const meta = document.getElementById("also-meta");
    const table = document.getElementById("also-table");
    const output = document.getElementById("also-output");

    const renderAlsoBought = (result) => {
      output.textContent = JSON.stringify(result.payload, null, 2);
      table.replaceChildren();
      const data = result.payload?.data?.alsoBought;
      if (!data) {
        meta.textContent = "No alsoBought data returned.";
        return;
      }
      meta.textContent = `source=${data.source} · generatedAt=${data.generatedAt}`;

      const header = document.createElement("div");
      header.className = "table-row table-header";
      header.innerHTML = "<div>SKU</div><div>Score</div><div>Evidence</div>";
      table.appendChild(header);

      if (!data.items?.length) {
        const empty = document.createElement("div");
        empty.className = "table-row empty";
        empty.textContent = "No co-purchases yet.";
        table.appendChild(empty);
        return;
      }

      data.items.forEach((item) => {
        const row = document.createElement("div");
        row.className = "table-row";

        const sku = document.createElement("div");
        sku.textContent = item.sku;

        const score = document.createElement("div");
        score.textContent = String(item.score);

        const evidence = document.createElement("div");
        evidence.textContent = (item.evidence || []).join(", ");

        row.appendChild(sku);
        row.appendChild(score);
        row.appendChild(evidence);
        table.appendChild(row);
      });
    };

    const run = async () => {
      const sku = skuInput?.value?.trim();
      const limit = parseInt(limitInput?.value || "10", 10);
      if (!sku) {
        meta.textContent = "SKU is required.";
        return;
      }
      runButton.disabled = true;
      meta.textContent = "Running...";
      try {
        const result = await fetchGraphql({
          query: queryInput?.value || "",
          variables: { sku, limit },
        });
        renderAlsoBought(result);
      } catch (err) {
        meta.textContent = "GraphQL request failed.";
      } finally {
        runButton.disabled = false;
      }
    };

    runButton?.addEventListener("click", run);
    clearButton?.addEventListener("click", () => {
      meta.textContent = "";
      table.replaceChildren();
      output.textContent = "";
    });

    if (skuInput?.value?.trim()) {
      run();
    }
  }

  const graphSeedSection = document.querySelector("[data-graph-seed]");
  if (graphSeedSection) {
    const seedButton = document.getElementById("graph-seed-run");
    const status = document.getElementById("graph-seed-status");
    const customerInput = document.getElementById("reco-customer-id");
    const skuInput = document.getElementById("also-sku");
    const customerOptions = document.getElementById("customer-id-options");
    const skuOptions = document.getElementById("sku-options");

    const ensureOption = (datalist, value) => {
      if (!datalist || !value) return;
      const exists = Array.from(datalist.children).some((child) => child.value === value);
      if (exists) return;
      const option = document.createElement("option");
      option.value = value;
      datalist.appendChild(option);
    };

    seedButton?.addEventListener("click", async () => {
      seedButton.disabled = true;
      if (status) status.textContent = "Seeding demo purchases...";
      try {
        const result = await fetchJson("/ui/graph/seed", { method: "POST" });
        if (!result.ok) {
          if (status) status.textContent = `Seed failed (HTTP ${result.status}).`;
          return;
        }

        const payload = result.payload || {};
        if (status) {
          status.textContent = `Seeded orders ${String(payload.order_a_id || "").slice(0, 8)} / ${String(payload.order_b_id || "").slice(0, 8)} · shared SKU=${payload.shared_sku}`;
        }

        if (customerInput && payload.customer_a_id) {
          customerInput.value = payload.customer_a_id;
        }
        if (skuInput && payload.shared_sku) {
          skuInput.value = payload.shared_sku;
        }

        ensureOption(customerOptions, payload.customer_a_id);
        ensureOption(customerOptions, payload.customer_b_id);
        ensureOption(skuOptions, payload.shared_sku);

        document.getElementById("reco-run")?.click();
        document.getElementById("also-run")?.click();
      } catch (err) {
        if (status) status.textContent = "Seed request failed.";
      } finally {
        seedButton.disabled = false;
      }
    });
  }

  const sseSection = document.querySelector("[data-sse]");
  if (sseSection) {
    const startButton = document.getElementById("sse-start");
    const stopButton = document.getElementById("sse-stop");
    const clearButton = document.getElementById("sse-clear");
    const log = document.getElementById("sse-log");
    const orderInput = document.getElementById("sse-order-id");
    let source = null;

    const { append, clear } = createAppender(log);

    const formatEvent = (kind, eventName, raw) => {
      const timestamp = new Date().toISOString();
      const parsed = tryParseJson(raw);
      if (parsed.ok) {
        return `${timestamp} ${kind} ${eventName}\n${JSON.stringify(parsed.value, null, 2)}\n`;
      }
      return `${timestamp} ${kind} ${eventName} ${raw}`;
    };

    const registerKnownEventListeners = (src) => {
      const names = [
        "order.created",
        "inventory.reserved",
        "payment.intent_created",
        "payment.succeeded",
      ];
      names.forEach((name) => {
        src.addEventListener(name, (event) => {
          append(formatEvent("SSE", name, event.data));
        });
      });
      src.onmessage = (event) => append(formatEvent("SSE", "message", event.data));
    };

    startButton?.addEventListener("click", () => {
      if (source) {
        source.close();
      }
      const orderId = orderInput?.value?.trim();
      const url = orderId ? `/stream/orders?order_id=${encodeURIComponent(orderId)}` : "/stream/orders";
      source = new EventSource(url);
      append(`Connecting to ${url} ...`);
      source.onopen = () => append("SSE connected");
      registerKnownEventListeners(source);
      source.addEventListener("error", () => append("SSE error or disconnected"));
    });

    stopButton?.addEventListener("click", () => {
      if (source) {
        source.close();
        source = null;
        append("SSE stopped");
      }
    });

    clearButton?.addEventListener("click", () => {
      clear();
    });

    startButton?.click();
  }

  const wsSection = document.querySelector("[data-ws]");
  if (wsSection) {
    const connectButton = document.getElementById("ws-connect");
    const disconnectButton = document.getElementById("ws-disconnect");
    const clearButton = document.getElementById("ws-clear");
    const log = document.getElementById("ws-log");
    let socket = null;

    const { append, clear } = createAppender(log);

    connectButton?.addEventListener("click", () => {
      if (socket) {
        socket.close();
      }
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${protocol}://${window.location.host}/ws/shipments`);
      socket.onopen = () => append("WS connected");
      socket.onmessage = (event) => {
        const timestamp = new Date().toISOString();
        const parsed = tryParseJson(event.data);
        if (parsed.ok) {
          append(`${timestamp} WS message\n${JSON.stringify(parsed.value, null, 2)}\n`);
          return;
        }
        append(`${timestamp} WS message ${event.data}`);
      };
      socket.onerror = () => append("WS error");
      socket.onclose = () => append("WS closed");
    });

    disconnectButton?.addEventListener("click", () => {
      if (socket) {
        socket.close();
        socket = null;
      }
    });

    clearButton?.addEventListener("click", () => {
      clear();
    });

    connectButton?.click();
  }

  const opsSimulatorSection = document.querySelector("[data-ops-simulator]");
  if (opsSimulatorSection) {
    const runButton = document.getElementById("ops-run");
    const status = document.getElementById("ops-status");
    const orderInput = document.getElementById("sse-order-id");

    runButton?.addEventListener("click", async () => {
      runButton.disabled = true;
      if (status) status.textContent = "Running workflow...";
      try {
        const result = await fetchJson("/ui/realtime/simulate", { method: "POST" });
        if (!result.ok) {
          if (status) status.textContent = `Workflow failed (HTTP ${result.status}).`;
          return;
        }
        const payload = result.payload || {};
        const orderId = payload.order?.id || "";
        const paymentId = payload.payment?.id || "";
        const reservationStatus = payload.reservation_status || "";

        if (status) {
          status.textContent = `Order ${String(orderId).slice(0, 8)} · reservation=${reservationStatus} · payment=${String(paymentId).slice(0, 8) || "n/a"}`;
        }

        if (orderInput && orderId) {
          orderInput.value = orderId;
          document.getElementById("sse-start")?.click();
        }
      } catch (err) {
        if (status) status.textContent = "Workflow request failed.";
      } finally {
        runButton.disabled = false;
      }
    });
  }

  const hoppscotchRealtimeSection = document.querySelector("[data-hoppscotch-realtime]");
  if (hoppscotchRealtimeSection) {
    const httpBase = `${window.location.protocol}//${window.location.host}`;
    const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    const sseUrl = `${httpBase}/stream/orders`;
    const wsUrl = `${wsProtocol}://${window.location.host}/ws/shipments`;

    const sseEl = document.getElementById("hoppscotch-sse-url");
    const wsEl = document.getElementById("hoppscotch-ws-url");
    if (sseEl) sseEl.textContent = sseUrl;
    if (wsEl) wsEl.textContent = wsUrl;
  }

  const orderBuilderForm = document.querySelector("form[data-order-builder]");
  if (orderBuilderForm) {
    const itemsTextarea = document.getElementById("order-items-json");
    const table = document.getElementById("order-preview-table");
    const total = document.getElementById("order-preview-total");
    const error = document.getElementById("order-preview-error");

    const renderPreview = () => {
      table.replaceChildren();
      error.hidden = true;
      total.textContent = "";

      const parsed = tryParseJson(itemsTextarea.value || "[]");
      if (!parsed.ok) {
        error.textContent = "Items JSON is invalid.";
        error.hidden = false;
        return { ok: false };
      }

      if (!Array.isArray(parsed.value)) {
        error.textContent = "Items JSON must be a list of objects.";
        error.hidden = false;
        return { ok: false };
      }

      const header = document.createElement("div");
      header.className = "table-row table-header";
      header.innerHTML = "<div>SKU</div><div>Qty</div><div>Unit</div><div>Total</div>";
      table.appendChild(header);

      let totalValue = 0;
      const validationErrors = [];
      parsed.value.forEach((item) => {
        const sku = String(item?.sku || "");
        const qty = Number(item?.qty || 0);
        const unitPrice = Number(item?.unit_price || item?.unitPrice || 0);
        const lineTotal = Math.round(qty * unitPrice * 100) / 100;

        totalValue += lineTotal;

        if (!sku || !Number.isFinite(qty) || qty <= 0 || !Number.isFinite(unitPrice) || unitPrice <= 0) {
          validationErrors.push(
            `Each item must include sku, qty > 0, unit_price > 0. Problem: sku='${sku}', qty='${item?.qty}', unit_price='${item?.unit_price}'`,
          );
        }

        const row = document.createElement("div");
        row.className = "table-row";

        const skuCell = document.createElement("div");
        skuCell.textContent = sku;

        const qtyCell = document.createElement("div");
        qtyCell.textContent = String(qty);

        const unitCell = document.createElement("div");
        unitCell.textContent = unitPrice ? `$${unitPrice.toFixed(2)}` : "$0.00";

        const totalCell = document.createElement("div");
        totalCell.textContent = lineTotal ? `$${lineTotal.toFixed(2)}` : "$0.00";

        row.appendChild(skuCell);
        row.appendChild(qtyCell);
        row.appendChild(unitCell);
        row.appendChild(totalCell);
        table.appendChild(row);
      });

      total.textContent = `Estimated total: $${(Math.round(totalValue * 100) / 100).toFixed(2)}`;
      if (validationErrors.length) {
        error.textContent = validationErrors.slice(0, 2).join("\n");
        error.hidden = false;
        return { ok: false };
      }
      return { ok: true };
    };

    itemsTextarea?.addEventListener("input", renderPreview);
    itemsTextarea?.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "f") {
        itemsTextarea.value = formatJson(itemsTextarea.value || "[]");
        renderPreview();
      }
    });
    orderBuilderForm.addEventListener("submit", (event) => {
      const result = renderPreview();
      if (!result.ok) event.preventDefault();
    });
    renderPreview();
  }
})();
