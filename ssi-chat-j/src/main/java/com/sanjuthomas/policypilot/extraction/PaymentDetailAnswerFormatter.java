package com.sanjuthomas.policypilot.extraction;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import java.util.Map;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/** Maps payment-service GET JSON → Thymeleaf payment detail card. */
@Component
public class PaymentDetailAnswerFormatter {

  private static final String TEMPLATE = "payment-detail";

  private final AnswerRenderer answerRenderer;
  private final MoneyFormat moneyFormat;

  public PaymentDetailAnswerFormatter(AnswerRenderer answerRenderer, MoneyFormat moneyFormat) {
    this.answerRenderer = answerRenderer;
    this.moneyFormat = moneyFormat;
  }

  public String format(Map<String, Object> data) {
    return answerRenderer.render(TEMPLATE, toView(data));
  }

  PaymentDetailAnswerView toView(Map<String, Object> data) {
    String currency = str(data.get("currency"));
    return new PaymentDetailAnswerView(
        dash(str(data.get("payment_id"))),
        dash(str(data.get("instruction_id"))),
        dash(str(data.get("status"))),
        amountCell(data.get("amount"), currency),
        dash(str(data.get("value_date"))),
        dash(str(data.get("owning_lob"))),
        EntityUserDisplay.creator(data.get("created_by")),
        EntityUserDisplay.approver(data.get("approved_by")),
        blankToNull(str(data.get("created_at"))),
        blankToNull(str(data.get("approved_at"))));
  }

  private String amountCell(Object amount, String currency) {
    if (amount == null) {
      return "—";
    }
    String formatted = moneyFormat.format(amount, currency);
    if (StringUtils.hasText(currency) && formatted.endsWith(".00")) {
      return formatted.substring(0, formatted.length() - 3);
    }
    return formatted;
  }

  private static String dash(String value) {
    return StringUtils.hasText(value) ? value : "—";
  }

  private static String blankToNull(String value) {
    return StringUtils.hasText(value) ? value : null;
  }

  private static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }
}
