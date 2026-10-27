package vn.webdoc.lite;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@SpringBootTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:litetest;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DEFAULT_NULL_ORDERING=HIGH",
        "webdoc.seed-demo=true", "webdoc.demo-password=Demo@123", "webdoc.bootstrap-admin-password=Admin@123" })
@AutoConfigureMockMvc
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class LiteApiTest {
    @Autowired
    MockMvc mvc;
    @Autowired
    ObjectMapper json;

    // ---------- tiện ích ----------

    private JsonNode body(MvcResult r) throws Exception {
        return json.readTree(r.getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8));
    }

    private String token(String user, String password) throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("{\"email\":\"" + user + "\",\"password\":\"" + password + "\"}")).andExpect(status().isOk())
                .andReturn();
        return body(r).get("access_token").asText();
    }

    private String demo(String user) throws Exception {
        return token(user, "Demo@123");
    }

    private JsonNode getJson(String url, String token) throws Exception {
        return body(mvc.perform(get(url).header("Authorization", "Bearer " + token)).andExpect(status().isOk())
                .andReturn());
    }

    private static Set<String> names(JsonNode array) {
        List<String> out = new ArrayList<>();
        array.forEach(n -> out.add(n.asText()));
        return out.stream().collect(Collectors.toSet());
    }

    private static List<String> filenames(JsonNode page) {
        List<String> out = new ArrayList<>();
        page.get("list").forEach(n -> out.add(n.get("originalFilename").asText()));
        return out;
    }

    // ---------- đăng nhập và bảo mật mặc định ----------

    @Test
    @Order(1)
    void loginAcceptsUsernameAndEmailAndRejectsWrongPassword() throws Exception {
        token("qtdl.gd2", "Demo@123");
        token("qtdl.gd2@sxd-th.example", "Demo@123");
        mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("{\"email\":\"qtdl.gd2\",\"password\":\"sai-mat-khau\"}")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("{\"email\":\"khong.ton.tai\",\"password\":\"Demo@123\"}")).andExpect(status().isUnauthorized());
    }

    @Test
    @Order(2)
    void everythingExceptWhitelistRequiresLoginIncludingFuturePaths() throws Exception {
        mvc.perform(get("/api/v1/ping")).andExpect(status().isOk());
        mvc.perform(get("/api/v1/users/profile")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/agent/ask?q=x")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/webdoc/ask").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/users/profile").header("Authorization", "Bearer abc.def.ghi"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @Order(3)
    void refreshTokenCannotBeUsedAsAccessTokenAndViceVersa() throws Exception {
        MvcResult r = mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("{\"email\":\"khaithac.so\",\"password\":\"Demo@123\"}")).andReturn();
        String access = body(r).get("access_token").asText();
        String refresh = body(r).get("refresh_token").asText();
        mvc.perform(get("/api/v1/users/profile").header("Authorization", "Bearer " + refresh))
                .andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/auth/refresh-token").contentType(MediaType.APPLICATION_JSON)
                .content("{\"refresh_token\":\"" + access + "\"}")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/auth/refresh-token").contentType(MediaType.APPLICATION_JSON)
                .content("{\"refresh_token\":\"" + refresh + "\"}")).andExpect(status().isOk());
    }

    // ---------- quyền gaa.* theo đề ----------

    @Test
    @Order(10)
    void demoAccountsHaveTheGaaPermissionsFromTheExercise() throws Exception {
        Set<String> all = Set.of("gaa.search", "gaa.analytics", "gaa.run_code", "gaa.export", "gaa.view_proposed",
                "gaa.restricted", "gaa.table.khach_hang");
        assertEquals(all, names(getJson("/api/v1/users/profile", demo("qtkt.gd2")).get("permissionNames")));
        assertEquals(Set.of("gaa.search", "gaa.analytics", "gaa.run_code", "gaa.export", "gaa.view_proposed",
                "gaa.restricted"), names(getJson("/api/v1/users/profile", demo("qtdl.gd2")).get("permissionNames")));
        JsonNode capnhat = getJson("/api/v1/users/profile", demo("capnhat.ht"));
        assertEquals(Set.of("gaa.search", "gaa.analytics", "gaa.run_code", "gaa.view_proposed"),
                names(capnhat.get("permissionNames")));
        assertEquals(Set.of("Hạc Thành"), names(capnhat.get("areas")));
        JsonNode doichieu = getJson("/api/v1/users/profile", demo("doichieu.ds"));
        assertEquals(Set.of("gaa.search", "gaa.analytics", "gaa.run_code"), names(doichieu.get("permissionNames")));
        assertEquals(Set.of("Đông Sơn"), names(doichieu.get("areas")));
        JsonNode khaithac = getJson("/api/v1/users/profile", demo("khaithac.so"));
        assertEquals(Set.of("gaa.search", "gaa.analytics", "gaa.run_code"), names(khaithac.get("permissionNames")));
        assertTrue(khaithac.get("areas").isEmpty());
        assertTrue(getJson("/api/v1/users/profile", demo("qtkt.gd2")).get("mfa").asBoolean());
        assertFalse(khaithac.get("mfa").asBoolean());
    }

    @Test
    @Order(11)
    void revokingARolePermissionTakesEffectOnTheVeryNextRequestWithTheSameToken() throws Exception {
        String admin = demo("qtkt.gd2");
        String khaithac = demo("khaithac.so");
        assertTrue(names(getJson("/api/v1/users/profile", khaithac).get("permissionNames")).contains("gaa.analytics"));

        JsonNode roles = getJson("/api/v1/roles", admin);
        long memberId = 0;
        for (JsonNode r : roles) {
            if ("MEMBER".equals(r.get("code").asText())) {
                memberId = r.get("id").asLong();
            }
        }
        mvc.perform(put("/api/v1/roles/" + memberId + "/permissions").header("Authorization", "Bearer " + admin)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"permissionNames\":[\"gaa.search\",\"gaa.run_code\"]}")).andExpect(status().isOk());
        try {
            assertFalse(names(getJson("/api/v1/users/profile", khaithac).get("permissionNames")).contains("gaa.analytics"));
        } finally {
            mvc.perform(put("/api/v1/roles/" + memberId + "/permissions").header("Authorization", "Bearer " + admin)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{\"permissionNames\":[\"gaa.search\",\"gaa.analytics\",\"gaa.run_code\"]}"))
                    .andExpect(status().isOk());
        }
        assertTrue(names(getJson("/api/v1/users/profile", khaithac).get("permissionNames")).contains("gaa.analytics"));
    }

    @Test
    @Order(12)
    void lockedUserIsRejectedImmediatelyEvenWithAValidToken() throws Exception {
        String admin = demo("qtkt.gd2");
        String doichieu = demo("doichieu.ds");
        long id = getJson("/api/v1/users/profile", doichieu).get("id").asLong();
        mvc.perform(put("/api/v1/users/status").header("Authorization", "Bearer " + admin)
                .contentType(MediaType.APPLICATION_JSON).content("{\"userId\":" + id + ",\"status\":2}"))
                .andExpect(status().isOk());
        try {
            mvc.perform(get("/api/v1/users/profile").header("Authorization", "Bearer " + doichieu))
                    .andExpect(status().isUnauthorized());
            mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                    .content("{\"email\":\"doichieu.ds\",\"password\":\"Demo@123\"}")).andExpect(status().isForbidden());
        } finally {
            mvc.perform(put("/api/v1/users/status").header("Authorization", "Bearer " + admin)
                    .contentType(MediaType.APPLICATION_JSON).content("{\"userId\":" + id + ",\"status\":1}"))
                    .andExpect(status().isOk());
        }
        mvc.perform(get("/api/v1/users/profile").header("Authorization", "Bearer " + doichieu)).andExpect(status().isOk());
    }

    // ---------- quản trị người dùng ----------

    @Test
    @Order(20)
    void onlyAdminsCanManageUsersAndRolesButMembersCanReadTheirOwnProfile() throws Exception {
        String member = demo("khaithac.so");
        mvc.perform(post("/api/v1/users").header("Authorization", "Bearer " + member)
                .contentType(MediaType.APPLICATION_JSON).content("{\"username\":\"x\"}")).andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/roles").header("Authorization", "Bearer " + member)).andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/organizations").header("Authorization", "Bearer " + demo("qtdl.gd2")))
                .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1));
    }

    @Test
    @Order(21)
    void adminCanCreateAUserThenGrantAdminUsingEitherFieldName() throws Exception {
        String admin = demo("qtkt.gd2");
        long orgId = getJson("/api/v1/users/profile", admin).get("organizationId").asLong();
        MvcResult created = mvc.perform(post("/api/v1/users").header("Authorization", "Bearer " + admin)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"nguoi.moi\",\"email\":\"nguoi.moi@sxd-th.example\",\"password\":\"MatKhau123\","
                        + "\"firstName\":\"Moi\",\"lastName\":\"Nguoi\",\"organizationId\":" + orgId
                        + ",\"roleCodes\":[\"MEMBER\"],\"areas\":[\"Hàm Rồng\"]}"))
                .andExpect(status().isCreated()).andReturn();
        long id = body(created).get("id").asLong();
        assertEquals(Set.of("Hàm Rồng"), names(body(created).get("areas")));
        mvc.perform(post("/api/v1/users").header("Authorization", "Bearer " + admin)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\":\"nguoi.moi\",\"email\":\"a@b.c\",\"password\":\"MatKhau123\"}"))
                .andExpect(status().isBadRequest());
        mvc.perform(put("/api/v1/users/role").header("Authorization", "Bearer " + admin)
                .contentType(MediaType.APPLICATION_JSON).content("{\"userId\":" + id + ",\"admin\":true}"))
                .andExpect(status().isOk());
        assertTrue(getJson("/api/v1/users/" + id, admin).get("admin").asBoolean());
        mvc.perform(put("/api/v1/users/role").header("Authorization", "Bearer " + admin)
                .contentType(MediaType.APPLICATION_JSON).content("{\"userId\":" + id + ",\"isAdmin\":false}"))
                .andExpect(status().isOk());
        assertFalse(getJson("/api/v1/users/" + id, admin).get("admin").asBoolean());
        mvc.perform(put("/api/v1/users/role").header("Authorization", "Bearer " + admin)
                .contentType(MediaType.APPLICATION_JSON).content("{\"userId\":" + id + "}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @Order(22)
    void profileUpdateValidatesNameLengthAndNormalizesWhitespace() throws Exception {
        String t = demo("capnhat.ht");
        mvc.perform(put("/api/v1/users/profile").header("Authorization", "Bearer " + t)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"firstName\":\"B\",\"lastName\":\"" + "A".repeat(31) + "\",\"gender\":true}"))
                .andExpect(status().isBadRequest());
        mvc.perform(put("/api/v1/users/profile").header("Authorization", "Bearer " + t)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"firstName\":\"  Hùng  \",\"lastName\":\"  Phạm   Văn \",\"gender\":true}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.lastName").value("Phạm Văn"))
                .andExpect(jsonPath("$.firstName").value("Hùng"));
    }

    // ---------- tài liệu và phạm vi xem ----------

    @Test
    @Order(30)
    void pngUnder100KbIsExactlyTheNineFilesAndTheExactly100KbFileIsExcluded() throws Exception {
        JsonNode page = getJson("/api/v1/documents/filter?type=png&maxSizeKb=100&size=50", demo("khaithac.so"));
        assertEquals(9, page.get("total").asInt());
        assertFalse(filenames(page).contains("so_do_tong_the.png"));
        assertTrue(filenames(getJson("/api/v1/documents/filter?type=png&maxSizeKb=100.001&size=50", demo("khaithac.so")))
                .contains("so_do_tong_the.png"));
    }

    @Test
    @Order(31)
    void usersWithAnAreaOnlySeeDocumentsOfThatArea() throws Exception {
        JsonNode page = getJson("/api/v1/documents/filter?size=100", demo("doichieu.ds"));
        assertTrue(page.get("total").asInt() > 0);
        page.get("list").forEach(d -> assertEquals("Đông Sơn", d.get("area").asText()));
        JsonNode capnhat = getJson("/api/v1/documents/filter?size=100", demo("capnhat.ht"));
        capnhat.get("list").forEach(d -> assertEquals("Hạc Thành", d.get("area").asText()));
        assertTrue(getJson("/api/v1/documents/filter?size=100", demo("khaithac.so")).get("total").asInt()
                > page.get("total").asInt());
    }

    @Test
    @Order(32)
    void privateAndDraftDocumentsFollowTheVisibilityRules() throws Exception {
        List<String> member = filenames(getJson("/api/v1/documents/filter?size=100", demo("khaithac.so")));
        assertFalse(member.contains("ghi_chu_noi_bo.docx"));
        assertFalse(member.contains("ke_hoach_nao_vet_2026.docx"));
        assertTrue(filenames(getJson("/api/v1/documents/filter?size=100", demo("qtdl.gd2"))).contains("ghi_chu_noi_bo.docx"));
        assertTrue(filenames(getJson("/api/v1/documents/filter?size=100", demo("qtdl.gd2")))
                .contains("ke_hoach_nao_vet_2026.docx"));
        assertTrue(filenames(getJson("/api/v1/documents/filter?size=100", demo("doichieu.ds")))
                .contains("ke_hoach_nao_vet_2026.docx"));
        assertFalse(filenames(getJson("/api/v1/documents/filter?size=100", demo("qtkt.gd2"))).contains("ghi_chu_noi_bo.docx"));
    }

    @Test
    @Order(33)
    void textSearchFindsQuangTrungFilesAndTheDuplicateHasTheSameHash() throws Exception {
        JsonNode page = getJson("/api/v1/documents/filter?text=tuyến cống Quang Trung&size=50", demo("khaithac.so"));
        assertEquals(2, page.get("total").asInt());
        assertEquals(page.get("list").get(0).get("contentHash").asText(), page.get("list").get(1).get("contentHash").asText());
        long hs01 = 0;
        for (JsonNode d : page.get("list")) {
            if ("HS-01.pdf".equals(d.get("originalFilename").asText())) {
                hs01 = d.get("id").asLong();
            }
        }
        JsonNode detail = getJson("/api/v1/documents/" + hs01, demo("khaithac.so"));
        assertEquals(3, detail.get("pages").size());
        assertTrue(detail.get("pages").get(1).asText().contains("Quang Trung"));
        mvc.perform(get("/api/v1/documents/" + 999999).header("Authorization", "Bearer " + demo("khaithac.so")))
                .andExpect(status().isNotFound());
    }

    @Test
    @Order(34)
    void areaRestrictedUserCannotReadADocumentOfAnotherAreaById() throws Exception {
        JsonNode all = getJson("/api/v1/documents/filter?area=Hạc Thành&size=5", demo("khaithac.so"));
        long otherAreaId = all.get("list").get(0).get("id").asLong();
        mvc.perform(get("/api/v1/documents/" + otherAreaId).header("Authorization", "Bearer " + demo("doichieu.ds")))
                .andExpect(status().isNotFound());
        assertNotEquals(0, otherAreaId);
    }

    // ---------- tổ chức và phòng ban ----------

    @Test
    @Order(40)
    void orgManagerCanManageDepartmentsOfOwnOrgButMembersCannot() throws Exception {
        String manager = demo("qtdl.gd2");
        String member = demo("khaithac.so");
        long orgId = getJson("/api/v1/users/profile", manager).get("organizationId").asLong();
        mvc.perform(post("/api/v1/departments").header("Authorization", "Bearer " + member)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Phòng thử\",\"organizationId\":" + orgId + "}")).andExpect(status().isForbidden());
        MvcResult r = mvc.perform(post("/api/v1/departments").header("Authorization", "Bearer " + manager)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Phòng thử\",\"description\":\"x\",\"organizationId\":" + orgId + "}"))
                .andExpect(status().isCreated()).andReturn();
        long id = body(r).get("id").asLong();
        mvc.perform(post("/api/v1/departments").header("Authorization", "Bearer " + manager)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"phòng thử\",\"organizationId\":" + orgId + "}")).andExpect(status().isBadRequest());
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete("/api/v1/departments/" + id)
                .header("Authorization", "Bearer " + manager)).andExpect(status().isOk());
        JsonNode list = getJson("/api/v1/departments/organization/" + orgId, manager);
        list.forEach(d -> assertNotEquals(id, d.get("id").asLong()));
    }
}
