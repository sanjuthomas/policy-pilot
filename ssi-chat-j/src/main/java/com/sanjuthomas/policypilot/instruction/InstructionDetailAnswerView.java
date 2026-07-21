package com.sanjuthomas.policypilot.instruction;

/**
 * View model for “show me instruction {id}” — fields mirror the Python instruction detail card.
 */
public record InstructionDetailAnswerView(
    String instructionId,
    String status,
    String instructionType,
    String owningLob,
    String currency,
    String wireScope,
    String creditor,
    String effectiveDate,
    String endDate,
    String versionNumber,
    String creator,
    String approver,
    String createdAt,
    String approvedAt) {}
