import React from "react";
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

export default function PayrollScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <View style={styles.iconContainer}>
          <Ionicons
            name="wallet-outline"
            size={56}
            color="#173B8C"
          />
        </View>

        <Text style={styles.title}>Salary & Payslips</Text>

        <Text style={styles.subtitle}>
          Payroll management coming soon
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F7F9FC",
  },

  content: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 32,
  },

  iconContainer: {
    width: 100,
    height: 100,
    borderRadius: 30,
    backgroundColor: "#EBF0FA",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 24,
  },

  title: {
    fontSize: 22,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: 8,
  },

  subtitle: {
    fontSize: 15,
    fontWeight: "600",
    color: "#64748B",
    textAlign: "center",
  },
});
