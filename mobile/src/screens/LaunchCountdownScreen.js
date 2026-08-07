import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  Animated,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";

import QRScannerModal from "./QRScannerModal";

export default function LaunchCountdownScreen({ onContinue }) {
  const [timeStr, setTimeStr] = useState("");
  const [dateStr, setDateStr] = useState("");
  const [countdown, setCountdown] = useState(3);
  const [autoNavigate, setAutoNavigate] = useState(false);
  const [showScanner, setShowScanner] = useState(false);

  const pulseAnim = useState(new Animated.Value(1))[0];

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: true,
        })
      );
      setDateStr(
        now
          .toLocaleDateString("en-US", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
          })
          .toUpperCase()
      );
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // Pulsing ring animation
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.15,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, []);

  // Auto countdown logic
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setAutoNavigate(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <LinearGradient colors={["#0F172A", "#1E3A8A", "#173B8C"]} style={styles.container}>
      <QRScannerModal visible={showScanner} onClose={() => setShowScanner(false)} />
      <SafeAreaView style={{ flex: 1 }}>
        <View style={styles.content}>
          {/* Top System Status Tag */}
          <View style={styles.topStatusTag}>
            <View style={styles.livePulseDot} />
            <Text style={styles.topStatusText}>SYSTEM READY • v2.4.0</Text>
          </View>

          {/* Logo with Animated Pulsing Ring */}
          <View style={styles.logoWrapper}>
            <Animated.View style={[styles.pulseRing, { transform: [{ scale: pulseAnim }] }]} />
            <View style={styles.logoCircle}>
              <Ionicons name="time-outline" size={38} color="#173B8C" />
            </View>
          </View>

          {/* Title & Tagline */}
          <Text style={styles.title}>Employee Attendance</Text>
          <Text style={styles.subtitle}>Enterprise Workforce & Time Tracking</Text>

          {/* Real-time Web-Matching Clock Block */}
          <View style={styles.clockCard}>
            <View style={styles.clockHeader}>
              <Ionicons name="alarm-outline" size={14} color="rgba(255,255,255,0.75)" />
              <Text style={styles.clockHeaderLabel}>LIVE TIME SYNC</Text>
            </View>

            <Text style={styles.liveTime}>{timeStr || "12:00:00 AM"}</Text>
            <Text style={styles.liveDate}>{dateStr}</Text>

            <View style={styles.clockFooter}>
              <View style={styles.footerItem}>
                <Ionicons name="shield-checkmark" size={12} color="#22C55E" />
                <Text style={styles.footerText}>Biometric Enabled</Text>
              </View>
              <View style={styles.footerItem}>
                <Ionicons name="location" size={12} color="#60A5FA" />
                <Text style={styles.footerText}>GPS Geofence</Text>
              </View>
            </View>
          </View>

          {/* Countdown Indicator / Quick Start */}
          <View style={styles.actionSection}>
            <TouchableOpacity
              activeOpacity={0.85}
              style={styles.continueBtn}
              onPress={onContinue}
            >
              <Text style={styles.continueBtnText}>
                {countdown > 0 ? `Enter Portal (${countdown}s)` : "Enter Portal"}
              </Text>
              <Ionicons name="arrow-forward" size={18} color="#173B8C" />
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.85}
              style={styles.qrQuickBtn}
              onPress={() => setShowScanner(true)}
            >
              <Ionicons name="qr-code-outline" size={18} color="#FFFFFF" />
              <Text style={styles.qrQuickBtnText}>Quick Attendance QR Scan</Text>
            </TouchableOpacity>
          </View>
        </View>

        <Text style={styles.copyRightText}>
          © 2026 HRzest.com • All Rights Reserved
        </Text>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 24,
  },

  // Top Status Tag
  topStatusTag: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(255, 255, 255, 0.12)",
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    marginBottom: 32,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.15)",
  },
  livePulseDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#22C55E",
    marginRight: 8,
  },
  topStatusText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: 0.8,
  },

  // Logo & Pulsing Ring
  logoWrapper: {
    width: 100,
    height: 100,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 20,
  },
  pulseRing: {
    position: "absolute",
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: "rgba(255, 255, 255, 0.15)",
  },
  logoCircle: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: "#FFFFFF",
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.2,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 8,
  },

  // Titles
  title: {
    fontSize: 26,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: -0.6,
    textAlign: "center",
  },
  subtitle: {
    fontSize: 13,
    color: "rgba(255, 255, 255, 0.78)",
    marginTop: 6,
    textAlign: "center",
  },

  // Clock Card
  clockCard: {
    width: "100%",
    backgroundColor: "rgba(255, 255, 255, 0.09)",
    borderRadius: 24,
    padding: 20,
    alignItems: "center",
    marginVertical: 28,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.14)",
  },
  clockHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
  },
  clockHeaderLabel: {
    fontSize: 10,
    fontWeight: "800",
    color: "rgba(255, 255, 255, 0.75)",
    letterSpacing: 0.8,
    marginLeft: 6,
  },
  liveTime: {
    fontSize: 32,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: 1.5,
  },
  liveDate: {
    fontSize: 11,
    fontWeight: "600",
    color: "rgba(255, 255, 255, 0.8)",
    marginTop: 4,
    letterSpacing: 0.5,
  },
  clockFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    width: "100%",
    marginTop: 16,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: "rgba(255, 255, 255, 0.1)",
  },
  footerItem: {
    flexDirection: "row",
    alignItems: "center",
  },
  footerText: {
    fontSize: 11,
    fontWeight: "600",
    color: "rgba(255, 255, 255, 0.85)",
    marginLeft: 5,
  },

  // Action Buttons
  actionSection: {
    width: "100%",
  },
  continueBtn: {
    height: 52,
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
  continueBtnText: {
    fontSize: 15,
    fontWeight: "800",
    color: "#173B8C",
    marginRight: 8,
  },
  qrQuickBtn: {
    height: 48,
    backgroundColor: "rgba(255, 255, 255, 0.12)",
    borderRadius: 16,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    marginTop: 12,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.18)",
  },
  qrQuickBtnText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#FFFFFF",
    marginLeft: 8,
  },

  copyRightText: {
    fontSize: 10,
    color: "rgba(255, 255, 255, 0.45)",
    textAlign: "center",
    marginBottom: 16,
  },
});
