package com.sanjuthomas.policypilot.skill;

/**
 * In-flight skill run awaiting Go / No Go. One record for all four mutation skills — create leaves
 * {@code paymentId} / {@code paymentStatus} / {@code createdBy*} null. Mirrors the Python
 * {@code Pending*Payment} dataclasses collapsed into one carrier.
 */
public record PendingSkill(
    String pendingId,
    String skill,
    String userId,
    String paymentId,
    String instructionId,
    double amount,
    String valueDate,
    String currency,
    String owningLob,
    String paymentStatus,
    String instructionStatus,
    String instructionEndDate,
    String instructionType,
    int instructionVersion,
    String createdByUserId,
    String createdBySupervisorId,
    ConfirmationCard card,
    long expiresAtEpochMs) {}
