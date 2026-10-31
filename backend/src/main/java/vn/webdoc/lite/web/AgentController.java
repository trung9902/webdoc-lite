package vn.webdoc.lite.web;

import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;

/**
 * Proxy nhẹ: chuyển tiếp câu hỏi của người dùng tới dịch vụ Agent Python
 * (FastAPI) rồi trả kết quả về cho frontend.
 *
 * GET /api/v1/agent/ask?q=...
 *   → POST http://localhost:8000/api/v1/ask  {"question": "..."}
 *   ← {"answer": "..."}
 *
 * Nếu dịch vụ Python không chạy → HTTP 503 kèm thông báo rõ ràng.
 */
@RestController
@RequestMapping("/api/v1/agent")
public class AgentController {

    private final RestTemplate rest;
    private final String agentBaseUrl;

    public AgentController(RestTemplateBuilder builder,
                           @Value("${webdoc.agent-service-url:http://localhost:8000}") String agentBaseUrl) {
        // Spring Boot 3.x: set timeouts via the request factory directly
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5_000);   // 5 s
        factory.setReadTimeout(30_000);     // 30 s
        this.rest = builder.requestFactory(() -> factory).build();
        this.agentBaseUrl = agentBaseUrl;
    }

    @GetMapping("/ask")
    public ResponseEntity<?> ask(@RequestParam String q) {
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> body = rest.postForObject(
                    agentBaseUrl + "/api/v1/ask",
                    Map.of("question", q),
                    Map.class);
            return ResponseEntity.ok(body);
        } catch (ResourceAccessException ex) {
            return ResponseEntity.status(503)
                    .body(Map.of("message",
                            "Dịch vụ Agent (Python) hiện không khả dụng. "
                                    + "Hãy đảm bảo agent_service.py đang chạy tại " + agentBaseUrl + "."));
        }
    }
}
