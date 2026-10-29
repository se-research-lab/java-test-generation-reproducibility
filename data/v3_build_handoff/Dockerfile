ARG BASE_IMAGE=minhquy266/classes2test-pipeline:pilot-v1
FROM ${BASE_IMAGE}

USER root

ARG MAVEN_VERSION=3.9.15
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV MAVEN_HOME=/opt/apache-maven-${MAVEN_VERSION}
ENV MAVEN_CONFIG=/cache/m2
ENV MAVEN_OPTS="-Dmaven.repo.local=/cache/m2/repository"
ENV GRADLE_USER_HOME=/cache/gradle
ENV PATH="${MAVEN_HOME}/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        python3 \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# The V2 image is used only as a JDK 8 base. Maven is replaced with the exact
# global version recorded by the V3 winning recipes. Gradle recipes use the
# repository wrappers; the global Gradle bundled in the V2 image is not used.
RUN curl -fsSLo /tmp/apache-maven.tar.gz \
        "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz" \
    && curl -fsSLo /tmp/apache-maven.tar.gz.sha512 \
        "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz.sha512" \
    && printf '%s  %s\n' \
        "$(tr -d ' \r\n' < /tmp/apache-maven.tar.gz.sha512)" \
        "/tmp/apache-maven.tar.gz" \
        | sha512sum -c - \
    && tar -xzf /tmp/apache-maven.tar.gz -C /opt \
    && rm /tmp/apache-maven.tar.gz /tmp/apache-maven.tar.gz.sha512

WORKDIR /handoff

COPY handoff_config.json README_BUILD_HANDOFF.md ./
COPY scripts/ ./scripts/
COPY native_windows/ ./native_windows/

RUN mkdir -p /cache/m2 /cache/gradle /build_work /build_replay_results \
    && java -version \
    && javac -version \
    && mvn -version \
    && python3 --version

CMD ["python3", "scripts/replay_builds.py", "--config", "handoff_config.json", "--check-only"]
