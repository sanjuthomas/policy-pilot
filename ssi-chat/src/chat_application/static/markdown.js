function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatInlineMarkdown(text) {
  let html = escapeHtml(text);
  const codeSlots = [];
  html = html.replace(/`([^`]+)`/g, (_match, code) => {
    const token = `\u0000CODE${codeSlots.length}\u0000`;
    codeSlots.push(`<code>${code}</code>`);
    return token;
  });
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // Underscore italics must not run inside protected code spans (e.g. ALERT_UNAPPROVED_INSTRUCTION).
  html = html.replace(/_([^_\n]+)_/g, "<em>$1</em>");
  codeSlots.forEach((snippet, index) => {
    html = html.replace(`\u0000CODE${index}\u0000`, snippet);
  });
  return html;
}

function parseTableRow(line) {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|") || !trimmed.endsWith("|")) {
    return null;
  }
  return trimmed
    .slice(1, -1)
    .split("|")
    .map((cell) => cell.trim().replace(/\\\|/g, "|"));
}

function isTableSeparator(line) {
  const cells = parseTableRow(line);
  if (!cells) {
    return false;
  }
  return cells.every((cell) => /^:?-{1,}:?$/.test(cell));
}

function buildTableHtml(header, rows) {
  const thead = header
    .map((cell) => `<th>${formatInlineMarkdown(cell)}</th>`)
    .join("");
  const tbody = rows
    .map(
      (row) =>
        `<tr>${row.map((cell) => `<td>${formatInlineMarkdown(cell)}</td>`).join("")}</tr>`
    )
    .join("");
  return `<div class="table-wrap"><table class="md-table"><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table></div>`;
}

function isBulletLine(line) {
  return /^\s*[-*]\s+/.test(line);
}

function parseHeading(line) {
  const match = /^(#{1,6})\s+(.+?)\s*$/.exec(line);
  if (!match) {
    return null;
  }
  return { level: match[1].length, text: match[2] };
}

function renderPlainMarkdown(lines) {
  const parts = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const heading = parseHeading(line);
    if (heading) {
      parts.push(
        `<h${heading.level} class="md-h${heading.level}">` +
          `${formatInlineMarkdown(heading.text)}` +
          `</h${heading.level}>`
      );
      index += 1;
      continue;
    }

    if (isBulletLine(line)) {
      const items = [];
      while (index < lines.length && isBulletLine(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*]\s+/, ""));
        index += 1;
      }
      parts.push(
        `<ul class="md-list">${items
          .map((item) => `<li>${formatInlineMarkdown(item)}</li>`)
          .join("")}</ul>`
      );
      continue;
    }

    parts.push(`<p class="md-p">${formatInlineMarkdown(line)}</p>`);
    index += 1;
  }

  return parts.join("");
}

function renderAssistantMarkdown(text) {
  const lines = String(text || "").split("\n");
  const parts = [];
  let index = 0;

  while (index < lines.length) {
    const header = parseTableRow(lines[index]);
    if (header && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      index += 2;
      const rows = [];
      while (index < lines.length) {
        const row = parseTableRow(lines[index]);
        if (!row) {
          break;
        }
        rows.push(row);
        index += 1;
      }
      parts.push(buildTableHtml(header, rows));
      continue;
    }

    const plain = [];
    while (index < lines.length) {
      const maybeHeader = parseTableRow(lines[index]);
      if (maybeHeader && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
        break;
      }
      plain.push(lines[index]);
      index += 1;
    }

    if (plain.length) {
      parts.push(renderPlainMarkdown(plain));
    }
  }

  return parts.join("");
}
