package com.sanjuthomas.policypilot.me;

import java.util.Set;

/** Amount-limit clubs carried on subject/directory groups. */
public final class MeAmountClubs {

  public static final Set<String> ALL =
      Set.of("UP_TO_100_MILLION_CLUB", "UP_TO_1_BILLION_CLUB", "UP_TO_100_BILLION_CLUB");

  private MeAmountClubs() {}

  public static boolean isClub(String group) {
    return group != null && ALL.contains(group);
  }
}
