import React from "react";

import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function PerformanceEmptyState({

  title = "No Performance Reviews",

  subtitle =
    "There are currently no performance records available. Start by creating a new employee review.",

  buttonTitle = "Create Review",

  onPress,

}) {

  return (

    <View style={styles.container}>

      {/* ================= ILLUSTRATION ================= */}

      <View style={styles.illustrationWrapper}>

        <View style={styles.circleLarge} />

        <View style={styles.circleMedium} />

        <View style={styles.iconContainer}>

          <Ionicons
            name="analytics-outline"
            size={54}
            color={PERFORMANCE_THEME.colors.primary}
          />

        </View>

      </View>

      {/* ================= CONTENT ================= */}

      <Text style={styles.title}>
        {title}
      </Text>

      <Text style={styles.subtitle}>
        {subtitle}
      </Text>

      {/* ================= ACTION BUTTON ================= */}

      <TouchableOpacity
        activeOpacity={0.9}
        style={styles.button}
        onPress={onPress}
      >

        <Ionicons
          name="add-circle-outline"
          size={20}
          color="#FFFFFF"
        />

        <Text style={styles.buttonText}>
          {buttonTitle}
        </Text>

      </TouchableOpacity>

    </View>

  );

}

const styles = StyleSheet.create({

  container: {
    backgroundColor: "#FFFFFF",

    borderRadius: 30,

    paddingHorizontal: 28,

    paddingVertical: 40,

    alignItems: "center",

    borderWidth: 1,

    borderColor: "#EEF2F7",

    shadowColor: "#0F172A",

    shadowOpacity: 0.05,

    shadowRadius: 12,

    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 4,
  },

  illustrationWrapper: {
    width: 180,

    height: 180,

    justifyContent: "center",

    alignItems: "center",

    marginBottom: 28,
  },

  circleLarge: {
    position: "absolute",

    width: 180,

    height: 180,

    borderRadius: 90,

    backgroundColor: "#F8FAFC",
  },

  circleMedium: {
    position: "absolute",

    width: 130,

    height: 130,

    borderRadius: 65,

    backgroundColor:
      PERFORMANCE_THEME.colors.primaryLight,
  },

  iconContainer: {
    width: 88,

    height: 88,

    borderRadius: 44,

    backgroundColor: "#FFFFFF",

    justifyContent: "center",

    alignItems: "center",

    shadowColor:
      PERFORMANCE_THEME.colors.primary,

    shadowOpacity: 0.12,

    shadowRadius: 12,

    shadowOffset: {
      width: 0,
      height: 6,
    },

    elevation: 6,
  },
    title: {
    fontSize: 24,

    fontWeight: "900",

    textAlign: "center",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  subtitle: {
    marginTop: 14,

    fontSize: 15,

    lineHeight: 24,

    textAlign: "center",

    color:
      PERFORMANCE_THEME.colors.textMuted,

    paddingHorizontal: 8,

    marginBottom: 32,
  },

  button: {
    minWidth: 220,

    height: 58,

    borderRadius: 18,

    backgroundColor:
      PERFORMANCE_THEME.colors.primary,

    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",

    shadowColor:
      PERFORMANCE_THEME.colors.primary,

    shadowOpacity: 0.22,

    shadowRadius: 14,

    shadowOffset: {
      width: 0,
      height: 6,
    },

    elevation: 8,
  },

  buttonText: {
    marginLeft: 10,

    fontSize: 16,

    fontWeight: "800",

    color: "#FFFFFF",
  },

});