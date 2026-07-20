package com.sanjuthomas.policypilot.me;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/** Dispatch me-lane intents (parity with Python {@code dispatch_me_intent}). */
@Service
public class MeIntentService {

  private final MeIntentResolver resolver;
  private final WhoAmIService whoAmIService;
  private final MyPermissionsService myPermissionsService;
  private final CanActOnEntityService canActOnEntityService;
  private final WhoCanCreateService whoCanCreateService;
  private final WhoCoversLobService whoCoversLobService;
  private final UsersLikeMeService usersLikeMeService;
  private final WaitingForMeService waitingForMeService;
  private final WhoElseCanActService whoElseCanActService;

  public MeIntentService(
      MeIntentResolver resolver,
      WhoAmIService whoAmIService,
      MyPermissionsService myPermissionsService,
      CanActOnEntityService canActOnEntityService,
      WhoCanCreateService whoCanCreateService,
      WhoCoversLobService whoCoversLobService,
      UsersLikeMeService usersLikeMeService,
      WaitingForMeService waitingForMeService,
      WhoElseCanActService whoElseCanActService) {
    this.resolver = resolver;
    this.whoAmIService = whoAmIService;
    this.myPermissionsService = myPermissionsService;
    this.canActOnEntityService = canActOnEntityService;
    this.whoCanCreateService = whoCanCreateService;
    this.whoCoversLobService = whoCoversLobService;
    this.usersLikeMeService = usersLikeMeService;
    this.waitingForMeService = waitingForMeService;
    this.whoElseCanActService = whoElseCanActService;
  }

  public MeIntentResult answer(RouterDecision decision, String message, Subject subject) {
    MeIntent intent = resolver.resolve(decision, message);
    if (intent == null || !StringUtils.hasText(intent.kind())) {
      return new MeIntentResult(
          "I could not determine which me-centric question you asked. "
              + "Try “Who am I?”, “What are my permissions?”, or “Who covers LOB FICC?”.",
          "me.unresolved");
    }
    return dispatch(intent, subject);
  }

  MeIntentResult dispatch(MeIntent intent, Subject subject) {
    return switch (intent.kind()) {
      case "who_am_i" ->
          new MeIntentResult(whoAmIService.answer(subject), WhoAmIService.INTENT_ID);
      case "my_permissions" -> myPermissionsService.answer(subject);
      case "who_can_create" -> whoCanCreateService.answer(intent, subject);
      case "who_covers_lob" -> whoCoversLobService.answer(intent);
      case "users_like_me" -> usersLikeMeService.answer(subject);
      case "waiting_for_me" -> waitingForMeService.answer(subject);
      case "can_act_on_entity" -> canActOnEntityService.answer(intent, subject);
      case "who_else_can_act" -> whoElseCanActService.answer(intent, subject);
      default ->
          new MeIntentResult(
              "Unsupported meKind=" + intent.kind() + " for ssi-chat-j.",
              "me.unsupported");
    };
  }
}
