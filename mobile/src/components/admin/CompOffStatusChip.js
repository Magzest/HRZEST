import React from "react";

import {
  View,
  Text,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import COMPOFF_THEME from "../../constants/compOffTheme";

export default function CompOffStatusChip({
  status = "Pending",
}) {

  const getStatus = () => {
    switch (status) {

      case "Approved":
        return {
          color: COMPOFF_THEME.colors.success,
          background:
            COMPOFF_THEME.colors.successLight,
          icon: "checkmark-circle",
        };

      case "Rejected":
        return {
          color: COMPOFF_THEME.colors.danger,
          background:
            COMPOFF_THEME.colors.dangerLight,
          icon: "close-circle",
        };

      case "Paid":
        return {
          color: COMPOFF_THEME.colors.primary,
          background:
            COMPOFF_THEME.colors.primaryLight,
          icon: "wallet",
        };

      case "Processing":
        return {
          color: COMPOFF_THEME.colors.secondary,
          background: "#EEF2FF",
          icon: "sync",
        };

      case "Pending":
      default:
        return {
          color: COMPOFF_THEME.colors.warning,
          background:
            COMPOFF_THEME.colors.warningLight,
          icon: "time",
        };
    }
  };

  const config = getStatus();

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor:
            config.background,
        },
      ]}
    >
      <Ionicons
        name={config.icon}
        size={14}
        color={config.color}
      />

      <Text
        style={[
          styles.text,
          {
            color: config.color,
          },
        ]}
      >
        {status}
      </Text>

    </View>
  );
}

const styles = StyleSheet.create({

  container: {

    flexDirection: "row",

    alignItems: "center",

    alignSelf: "flex-start",

    paddingHorizontal: 12,

    paddingVertical: 7,

    borderRadius: 50,
  },

  text: {

    marginLeft: 6,

    fontSize: 12,

    fontWeight: "800",

    letterSpacing: 0.2,
  },

});