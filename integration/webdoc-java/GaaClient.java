// Mẫu phía WebDoc (Java 17+, chỉ dùng JDK): ký JWT HS256 cho người dùng hiện tại và gọi GAA /api/v1/ask.
// Trong Spring Boot: đặt lớp này thành @Service, lấy claim từ SecurityContext (Keycloak) thay cho tham số dòng lệnh.
//   javac GaaClient.java && GAA_JWT_SECRET=... java GaaClient doichieu.ds doi_chieu "Đông Sơn" "Tổng chiều dài cống từ D600 trở lên theo phường và vật liệu"
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;

public class GaaClient {
    private final String baseUrl;
    private final byte[] secret;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();

    public GaaClient(String baseUrl, String secret) {
        if (secret == null || secret.length() < 32) throw new IllegalArgumentException("GAA_JWT_SECRET >= 32 ký tự");
        this.baseUrl = baseUrl;
        this.secret = secret.getBytes(StandardCharsets.UTF_8);
    }

    static String b64(byte[] b) { return Base64.getUrlEncoder().withoutPadding().encodeToString(b); }
    static String q(String s) { return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\""; }

    /** Token ngắn hạn (5 phút) mang danh tính người dùng WebDoc; GAA dùng nó cả khi gọi ngược API dữ liệu WebDoc. */
    public String sign(String sub, String bizRole, String[] areas, boolean mfa) throws Exception {
        long now = Instant.now().getEpochSecond();
        StringBuilder a = new StringBuilder("[");
        for (int i = 0; i < areas.length; i++) a.append(i > 0 ? "," : "").append(q(areas[i]));
        a.append("]");
        String header = b64("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
        String payload = b64(("{\"iss\":\"webdoc\",\"aud\":\"gaa\",\"iat\":" + now + ",\"exp\":" + (now + 300)
                + ",\"sub\":" + q(sub) + ",\"biz_role\":" + q(bizRole) + ",\"areas\":" + a + ",\"mfa\":" + mfa + "}")
                .getBytes(StandardCharsets.UTF_8));
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret, "HmacSHA256"));
        String sig = b64(mac.doFinal((header + "." + payload).getBytes(StandardCharsets.UTF_8)));
        return header + "." + payload + "." + sig;
    }

    public String ask(String token, String question) throws Exception {
        HttpRequest req = HttpRequest.newBuilder(URI.create(baseUrl + "/api/v1/ask"))
                .timeout(Duration.ofSeconds(120))
                .header("Content-Type", "application/json; charset=utf-8")
                .header("Authorization", "Bearer " + token)
                .POST(HttpRequest.BodyPublishers.ofString("{\"question\":" + q(question) + "}", StandardCharsets.UTF_8))
                .build();
        HttpResponse<String> r = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (r.statusCode() != 200) throw new IllegalStateException("GAA trả " + r.statusCode() + ": " + r.body());
        return r.body();
    }

    public static void main(String[] args) throws Exception {
        String url = System.getenv().getOrDefault("GAA_URL", "http://127.0.0.1:8080");
        GaaClient c = new GaaClient(url, System.getenv("GAA_JWT_SECRET"));
        String[] areas = args[2].isEmpty() ? new String[0] : args[2].split(",");
        String token = c.sign(args[0], args[1], areas, false);
        String body = c.ask(token, args[3]);
        int i = body.indexOf("\"answer\":");
        int j = body.indexOf("\", \"", i);
        System.out.println("HTTP 200 · " + body.length() + " byte");
        System.out.println(body.substring(i, j + 1));
    }
}
