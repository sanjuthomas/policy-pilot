package com.sanjuthomas.policypilot.extraction;

/** Result of a document_extraction lane answer. */
public record DocumentExtractionResult(String answer, String intentId) {}
