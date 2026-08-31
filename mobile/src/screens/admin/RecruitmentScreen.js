import React, { useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import AdminHeader from "../../components/admin/AdminHeader";
import { useTheme } from "../../store/ThemeContext";
import {
  parseResumeText, screenCandidate, evaluateInterview, fetchAttritionAnalytics,
} from "../../api/client";

// Mobile twin of templates/recruitment.html's three tools (blueprints/ai_hrms.py) --
// resume upload isn't supported here (no document-picker dependency yet), so
// screening takes pasted resume text, same as the web page's own text-paste
// fallback path (parse_resume() accepts either a file or raw text).
export default function RecruitmentScreen({ navigation }) {
  const { colors } = useTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const [activeTab, setActiveTab] = useState("screening");

  return (
    <LinearGradient colors={colors.screenGradient} style={styles.container}>
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="AI Recruitment"
          onMenu={() => navigation.dispatch(DrawerActions.openDrawer())}
        />

        <View style={styles.tabBar}>
          {[
            { key: "screening", label: "Screening", icon: "document-text" },
            { key: "interview", label: "Interview", icon: "people" },
            { key: "attrition", label: "Attrition", icon: "pulse" },
          ].map((t) => (
            <TouchableOpacity
              key={t.key}
              style={[styles.tabBtn, activeTab === t.key && styles.tabBtnActive]}
              onPress={() => setActiveTab(t.key)}
            >
              <Ionicons name={t.icon} size={15} color={activeTab === t.key ? "#FFFFFF" : "#64748B"} />
              <Text style={[styles.tabText, activeTab === t.key && styles.tabTextActive]}>{t.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {activeTab === "screening" && <ScreeningTab />}
        {activeTab === "interview" && <InterviewTab />}
        {activeTab === "attrition" && <AttritionTab />}
      </SafeAreaView>
    </LinearGradient>
  );
}

function Card({ children, style }) {
  const { colors } = useTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  return <View style={[styles.card, style]}>{children}</View>;
}

function ScreeningTab() {
  const { colors } = useTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const [resumeText, setResumeText] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [parsedProfile, setParsedProfile] = useState(null);
  const [matchResult, setMatchResult] = useState(null);

  const handleScreen = async () => {
    if (!resumeText.trim()) {
      Alert.alert("Validation Error", "Paste the candidate's resume text first.");
      return;
    }
    setLoading(true);
    setParsedProfile(null);
    setMatchResult(null);
    try {
      const parseRes = await parseResumeText(resumeText.trim());
      if (!parseRes?.data?.ok) throw new Error(parseRes?.data?.msg || "Could not parse resume.");
      setParsedProfile(parseRes.data.parsed_profile);

      const screenRes = await screenCandidate(parseRes.data.parsed_profile, jobDescription.trim());
      if (screenRes?.data?.ok) setMatchResult(screenRes.data.match_result);
    } catch (e) {
      Alert.alert("Failed", e?.response?.data?.msg || e.message || "Could not screen this candidate.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <Card>
        <Text style={styles.cardTitle}>Resume Screening</Text>
        <Text style={styles.label}>RESUME TEXT</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Paste the candidate's resume text here..."
          value={resumeText}
          onChangeText={setResumeText}
          multiline
        />
        <Text style={styles.label}>JOB DESCRIPTION (OPTIONAL)</Text>
        <TextInput
          style={[styles.input, styles.textArea, { minHeight: 70 }]}
          placeholder="Paste the job description to score against..."
          value={jobDescription}
          onChangeText={setJobDescription}
          multiline
        />
        <TouchableOpacity style={styles.primaryBtn} onPress={handleScreen} disabled={loading}>
          {loading ? <ActivityIndicator color="#FFF" /> : (
            <>
              <Ionicons name="sparkles" size={16} color="#FFF" />
              <Text style={styles.primaryBtnText}>Parse & Screen Candidate</Text>
            </>
          )}
        </TouchableOpacity>
      </Card>

      {parsedProfile && (
        <Card>
          <Text style={styles.cardTitle}>Parsed Profile</Text>
          <InfoRow label="Name" value={parsedProfile.candidate_name} />
          <InfoRow label="Email" value={parsedProfile.email} />
          <InfoRow label="Phone" value={parsedProfile.phone} />
          <InfoRow label="Experience" value={`${parsedProfile.years_experience} years`} />
          <InfoRow label="Skills" value={(parsedProfile.skills || []).join(", ")} />
          <InfoRow label="Education" value={parsedProfile.education} />
        </Card>
      )}

      {matchResult && (
        <Card>
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>Match Result</Text>
            <View style={styles.scorePill}>
              <Text style={styles.scorePillText}>{matchResult.match_score}%</Text>
            </View>
          </View>
          <Text style={styles.tierText}>{matchResult.match_tier}</Text>
          <InfoRow label="Matched Skills" value={(matchResult.matched_skills || []).join(", ")} />
          <InfoRow label="Recommendation" value={matchResult.recommendation} />
          <Text style={styles.rationale}>{matchResult.rationale_summary}</Text>
        </Card>
      )}
    </ScrollView>
  );
}

function InterviewTab() {
  const { colors } = useTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const [candidateName, setCandidateName] = useState("");
  const [position, setPosition] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [evaluation, setEvaluation] = useState(null);

  const handleEvaluate = async () => {
    if (!notes.trim()) {
      Alert.alert("Validation Error", "Enter the interviewer's notes first.");
      return;
    }
    setLoading(true);
    setEvaluation(null);
    try {
      const res = await evaluateInterview(candidateName.trim() || "Candidate", position.trim() || "Software Engineer", notes.trim());
      if (res?.data?.ok) setEvaluation(res.data.evaluation);
      else Alert.alert("Failed", res?.data?.msg || "Could not evaluate these notes.");
    } catch (e) {
      Alert.alert("Failed", e?.response?.data?.msg || "Could not evaluate these notes.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <Card>
        <Text style={styles.cardTitle}>Interview Evaluation</Text>
        <Text style={styles.label}>CANDIDATE NAME</Text>
        <TextInput style={styles.input} placeholder="e.g. Priya Sharma" value={candidateName} onChangeText={setCandidateName} />
        <Text style={styles.label}>POSITION</Text>
        <TextInput style={styles.input} placeholder="e.g. Senior Backend Engineer" value={position} onChangeText={setPosition} />
        <Text style={styles.label}>INTERVIEWER NOTES</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Paste the interviewer's raw notes here..."
          value={notes}
          onChangeText={setNotes}
          multiline
        />
        <TouchableOpacity style={styles.primaryBtn} onPress={handleEvaluate} disabled={loading}>
          {loading ? <ActivityIndicator color="#FFF" /> : (
            <>
              <Ionicons name="analytics" size={16} color="#FFF" />
              <Text style={styles.primaryBtnText}>Evaluate Notes</Text>
            </>
          )}
        </TouchableOpacity>
      </Card>

      {evaluation && (
        <>
          <Card>
            <View style={styles.rowBetween}>
              <Text style={styles.cardTitle}>{evaluation.candidate_name} — {evaluation.position}</Text>
              <View style={styles.scorePill}>
                <Text style={styles.scorePillText}>{evaluation.overall_rating}/10</Text>
              </View>
            </View>
            <Text style={styles.tierText}>{evaluation.overall_recommendation}</Text>
            <Text style={styles.rationale}>{evaluation.executive_summary}</Text>
          </Card>

          <Card>
            <Text style={styles.cardTitle}>Competency Scores</Text>
            {Object.entries(evaluation.competencies || {}).map(([key, val]) => (
              <InfoRow key={key} label={key.replace(/_/g, " ")} value={`${val}/10`} />
            ))}
          </Card>

          <Card>
            <Text style={styles.cardTitle}>Sentiment</Text>
            <InfoRow label="Positive" value={evaluation.sentiment_analysis?.positive} />
            <InfoRow label="Neutral" value={evaluation.sentiment_analysis?.neutral} />
            <InfoRow label="Concerned" value={evaluation.sentiment_analysis?.concerned} />
          </Card>

          <Card>
            <Text style={styles.cardTitle}>Key Strengths</Text>
            {(evaluation.key_strengths || []).map((s, i) => <BulletLine key={i} text={s} color="#16A34A" />)}
          </Card>

          <Card>
            <Text style={styles.cardTitle}>Areas of Concern</Text>
            {(evaluation.areas_of_concern || []).map((s, i) => <BulletLine key={i} text={s} color="#D97706" />)}
          </Card>
        </>
      )}
    </ScrollView>
  );
}

function AttritionTab() {
  const { colors } = useTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState(null);

  React.useEffect(() => {
    (async () => {
      try {
        const res = await fetchAttritionAnalytics();
        if (res?.data?.ok) setAnalytics(res.data.analytics);
      } catch (_) {}
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color="#173B8C" />
      </View>
    );
  }

  if (!analytics) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", padding: 32 }}>
        <Ionicons name="cloud-offline-outline" size={40} color={colors.textLight} />
        <Text style={{ marginTop: 10, color: "#64748B" }}>Could not load attrition analytics.</Text>
      </View>
    );
  }

  const s = analytics.summary || {};
  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <Card>
        <Text style={styles.cardTitle}>Turnover Summary</Text>
        <View style={styles.summaryGrid}>
          <SummaryStat label="Turnover Index" value={s.overall_turnover_index} color="#DC2626" />
          <SummaryStat label="High Risk" value={s.high_burnout_risk_count} color="#DC2626" />
          <SummaryStat label="Medium Risk" value={s.medium_burnout_risk_count} color="#D97706" />
          <SummaryStat label="Low Risk" value={s.low_burnout_risk_count} color="#16A34A" />
        </View>
        <InfoRow label="Trend" value={s.predicted_attrition_trend} />
      </Card>

      <Card>
        <Text style={styles.cardTitle}>AI Insights</Text>
        {(analytics.ai_insights_summary || []).map((s2, i) => <BulletLine key={i} text={s2} color="#2563EB" />)}
      </Card>

      <Card>
        <Text style={styles.cardTitle}>Flagged Employees</Text>
        {(analytics.flagged_burnout_risks || []).length === 0 ? (
          <Text style={styles.rationale}>No employees currently flagged for burnout risk.</Text>
        ) : (
          analytics.flagged_burnout_risks.map((e) => (
            <View key={e.employee_id} style={styles.riskRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.riskName}>{e.name} <Text style={styles.riskDept}>· {e.department}</Text></Text>
                <Text style={styles.riskFactor}>{e.primary_risk_factor}</Text>
              </View>
              <View style={[styles.riskBadge, { backgroundColor: e.risk_level === "High" ? "#FEE2E2" : "#FEF3C7" }]}>
                <Text style={[styles.riskBadgeText, { color: e.risk_level === "High" ? "#991B1B" : "#92400E" }]}>
                  {e.risk_level}
                </Text>
              </View>
            </View>
          ))
        )}
      </Card>
    </ScrollView>
  );
}

function InfoRow({ label, value }) {
  const { colors } = useTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  if (!value) return null;
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{String(value)}</Text>
    </View>
  );
}

function BulletLine({ text, color }) {
  const { colors } = useTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  return (
    <View style={styles.bulletRow}>
      <View style={[styles.bulletDot, { backgroundColor: color }]} />
      <Text style={styles.bulletText}>{text}</Text>
    </View>
  );
}

function SummaryStat({ label, value, color }) {
  const { colors } = useTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  return (
    <View style={styles.summaryStat}>
      <Text style={[styles.summaryStatValue, { color }]}>{value ?? "--"}</Text>
      <Text style={styles.summaryStatLabel}>{label}</Text>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: { flex: 1 },
  tabBar: {
    flexDirection: "row",
    paddingHorizontal: 16,
    paddingBottom: 10,
    gap: 8,
  },
  tabBtn: {
    flex: 1,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 9,
    borderRadius: 12,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    gap: 6,
  },
  tabBtnActive: { backgroundColor: "#173B8C", borderColor: "#173B8C" },
  tabText: { fontSize: 12, fontWeight: "700", color: "#64748B" },
  tabTextActive: { color: "#FFFFFF" },

  content: { paddingHorizontal: 16, paddingBottom: 40 },

  card: {
    backgroundColor: colors.card,
    borderRadius: 18,
    padding: 18,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardTitle: { fontSize: 15, fontWeight: "800", color: colors.text, marginBottom: 12 },

  label: { fontSize: 11, fontWeight: "800", color: "#64748B", letterSpacing: 0.6, marginBottom: 6, marginTop: 10 },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 13,
    fontWeight: "600",
    color: colors.text,
  },
  textArea: { minHeight: 110, textAlignVertical: "top" },

  primaryBtn: {
    backgroundColor: "#173B8C",
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 14,
    borderRadius: 14,
    marginTop: 16,
    gap: 8,
  },
  primaryBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "800" },

  infoRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: "#F1F5F9" },
  infoLabel: { fontSize: 12, color: "#64748B", fontWeight: "700", textTransform: "capitalize" },
  infoValue: { fontSize: 12, color: colors.text, fontWeight: "600", flex: 1, textAlign: "right", marginLeft: 12 },

  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  scorePill: { backgroundColor: colors.primaryLight, paddingHorizontal: 12, paddingVertical: 5, borderRadius: 12 },
  scorePillText: { color: "#173B8C", fontWeight: "800", fontSize: 13 },
  tierText: { fontSize: 13, fontWeight: "700", color: "#173B8C", marginBottom: 8 },
  rationale: { fontSize: 12, color: colors.textSecondary, lineHeight: 18, marginTop: 6 },

  bulletRow: { flexDirection: "row", alignItems: "flex-start", marginBottom: 8, gap: 8 },
  bulletDot: { width: 6, height: 6, borderRadius: 3, marginTop: 5 },
  bulletText: { flex: 1, fontSize: 12, color: "#334155", lineHeight: 18 },

  summaryGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: 10 },
  summaryStat: { width: "47%", backgroundColor: colors.background, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border },
  summaryStatValue: { fontSize: 18, fontWeight: "800" },
  summaryStatLabel: { fontSize: 11, color: "#64748B", fontWeight: "700", marginTop: 2 },

  riskRow: { flexDirection: "row", alignItems: "center", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#F1F5F9" },
  riskName: { fontSize: 13, fontWeight: "700", color: colors.text },
  riskDept: { fontSize: 12, color: "#64748B", fontWeight: "500" },
  riskFactor: { fontSize: 11, color: colors.textLight, marginTop: 2 },
  riskBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  riskBadgeText: { fontSize: 11, fontWeight: "800" },
});
