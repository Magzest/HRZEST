import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";

import { getCompanySignupStatus } from "../api/client";
import { useTheme } from "../store/ThemeContext";

const STATUS_META = {
  pending_review: { icon: "time-outline", color: "#F59E0B", title: "Under Review", body: "Our team verifies every application's documents before activating a portal — you'll get an email as soon as a decision is made." },
  approved_pending_payment: { icon: "card-outline", color: "#F59E0B", title: "Approved — Payment Pending", body: "Check your email for a link to complete payment and activate your portal." },
  provisioned: { icon: "checkmark-circle-outline", color: "#16A34A", title: "Approved!", body: "Your portal is live. Sign in from the login screen using the admin password you set." },
  rejected: { icon: "close-circle-outline", color: "#DC2626", title: "Not Approved", body: "We're unable to approve this registration at this time." },
};

export default function CompanySignupPendingScreen({ navigation, route }) {
  const { colors } = useTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const { applicationId, accessToken, companyName } = route.params;

  const [status, setStatus] = useState("pending_review");
  const [rejectionReason, setRejectionReason] = useState(null);
  const [checking, setChecking] = useState(false);

  const checkStatus = useCallback(async () => {
    setChecking(true);
    try {
      const res = await getCompanySignupStatus(applicationId, accessToken);
      if (res?.data?.ok) {
        setStatus(res.data.status);
        setRejectionReason(res.data.rejection_reason);
      }
    } catch (_) {
      // Best-effort -- the applicant can always retry with the button.
    }
    setChecking(false);
  }, [applicationId, accessToken]);

  const meta = STATUS_META[status] || STATUS_META.pending_review;

  return (
    <LinearGradient colors={["#0F172A", "#1E3A8A", "#173B8C"]} style={styles.bg}>
      <View style={styles.content}>
        <View style={[styles.iconCircle, { backgroundColor: `${meta.color}22` }]}>
          <Ionicons name={meta.icon} size={40} color={meta.color} />
        </View>
        <Text style={styles.title}>{meta.title}</Text>
        <Text style={styles.company}>{companyName}</Text>
        <Text style={styles.body}>{meta.body}</Text>

        {status === "rejected" && rejectionReason ? (
          <View style={styles.reasonBox}>
            <Text style={styles.reasonText}>{rejectionReason}</Text>
          </View>
        ) : null}

        {status === "provisioned" ? (
          <TouchableOpacity style={styles.primaryBtn} onPress={() => navigation.navigate("Login")} activeOpacity={0.85}>
            <Text style={styles.primaryBtnText}>Go to Sign In</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={styles.secondaryBtn} onPress={checkStatus} disabled={checking} activeOpacity={0.85}>
            {checking ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.secondaryBtnText}>Check Status</Text>}
          </TouchableOpacity>
        )}

        <TouchableOpacity style={{ marginTop: 18 }} onPress={() => navigation.navigate("Login")}>
          <Text style={styles.backToLogin}>Back to Sign In</Text>
        </TouchableOpacity>
      </View>
    </LinearGradient>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  bg: { flex: 1 },
  content: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 32 },
  iconCircle: { width: 84, height: 84, borderRadius: 42, justifyContent: "center", alignItems: "center", marginBottom: 22 },
  title: { fontSize: 20, fontWeight: "800", color: "#FFFFFF", textAlign: "center" },
  company: { fontSize: 13, fontWeight: "600", color: "rgba(255,255,255,0.7)", marginTop: 4, textAlign: "center" },
  body: { fontSize: 13.5, color: "rgba(255,255,255,0.8)", textAlign: "center", marginTop: 14, lineHeight: 20 },
  reasonBox: { backgroundColor: "rgba(220,38,38,0.15)", borderRadius: 12, padding: 14, marginTop: 16, width: "100%" },
  reasonText: { fontSize: 13, color: "#FCA5A5", lineHeight: 18 },
  primaryBtn: { height: 48, borderRadius: 14, backgroundColor: "#16A34A", justifyContent: "center", alignItems: "center", marginTop: 26, width: "100%" },
  primaryBtnText: { fontSize: 13, fontWeight: "800", color: "#FFFFFF" },
  secondaryBtn: { height: 48, borderRadius: 14, backgroundColor: "rgba(255,255,255,0.15)", justifyContent: "center", alignItems: "center", marginTop: 26, width: "100%" },
  secondaryBtnText: { fontSize: 13, fontWeight: "800", color: "#FFFFFF" },
  backToLogin: { fontSize: 13, fontWeight: "600", color: "rgba(255,255,255,0.7)" },
});
