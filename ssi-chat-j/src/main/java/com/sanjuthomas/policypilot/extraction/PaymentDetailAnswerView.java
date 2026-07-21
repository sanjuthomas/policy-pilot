package com.sanjuthomas.policypilot.extraction;

/**
 * View model for “show me payment {id}” — fields mirror the Python payment detail card.
 */
public record PaymentDetailAnswerView(
    String paymentId,
    String instructionId,
    String status,
    String amount,
    String valueDate,
    String owningLob,
    String creator,
    String approver,
    String createdAt,
    String approvedAt) {}
