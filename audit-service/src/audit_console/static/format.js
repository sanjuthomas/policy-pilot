(function () {
  const AMOUNT_IN_BASIS =
    /amount\s+([\d.eE+-]+)\s+(within subject and absolute limits)/gi;

  function formatUsdCompact(amount) {
    const abs = Math.abs(amount);
    if (abs >= 1_000_000_000) {
      const value = abs / 1_000_000_000;
      return Number.isInteger(value)
        ? `$${value} billion`
        : `$${trimOneDecimal(value)} billion`;
    }
    if (abs >= 1_000_000) {
      const value = abs / 1_000_000;
      return Number.isInteger(value)
        ? `$${value} million`
        : `$${trimOneDecimal(value)} million`;
    }
    if (abs >= 1_000) {
      return `$${Math.round(abs).toLocaleString("en-US")}`;
    }
    if (Number.isInteger(abs)) {
      return `$${abs}`;
    }
    return `$${abs.toFixed(2)}`;
  }

  function trimOneDecimal(value) {
    const text = value.toFixed(1);
    return text.endsWith(".0") ? text.slice(0, -2) : text;
  }

  function humanizeAmountInBasis(text) {
    if (typeof text !== "string") {
      return text;
    }
    return text.replace(AMOUNT_IN_BASIS, (_, num, rest) => {
      const amount = Number(num);
      if (!Number.isFinite(amount)) {
        return `amount ${num} ${rest}`;
      }
      return `amount ${formatUsdCompact(amount)} ${rest}`;
    });
  }

  function humanizeOpaValue(value) {
    if (typeof value === "string") {
      return humanizeAmountInBasis(value);
    }
    if (Array.isArray(value)) {
      return value.map(humanizeOpaValue);
    }
    if (value && typeof value === "object") {
      const out = {};
      for (const [key, nested] of Object.entries(value)) {
        out[key] = humanizeOpaValue(nested);
      }
      return out;
    }
    return value;
  }

  function prettyJson(value) {
    return JSON.stringify(humanizeOpaValue(value), null, 2);
  }

  window.AuditorFormat = { formatUsdCompact, humanizeOpaValue, prettyJson };
})();
