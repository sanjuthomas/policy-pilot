package com.policypilot.chatj.api;

import java.util.Map;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class HomeController {

  @GetMapping("/")
  public String home(Model model) {
    model.addAttribute("serviceName", "ssi-chat-j");
    model.addAttribute("port", 8096);
    return "index";
  }

  @GetMapping("/api/index-integrity")
  @org.springframework.web.bind.annotation.ResponseBody
  public Map<String, Object> indexIntegrityStub() {
    // M1: no indexer wiring yet — keep UI banner quiet.
    java.util.HashMap<String, Object> body = new java.util.HashMap<>();
    body.put("show_banner", false);
    body.put("banner_message", null);
    return body;
  }
}
