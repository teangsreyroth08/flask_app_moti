pipeline {
  agent any

  environment {
    IMAGE_NAME     = 'demo-flask'
    CONTAINER_NAME = 'demo-flask-app'
    PORT           = '5000'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Docker sanity check') {
      steps {
        sh 'docker version'
      }
    }

    stage('Build Docker Image') {
      steps {
        sh "docker build -t ${env.IMAGE_NAME}:${env.BUILD_NUMBER} ."
        sh "docker tag ${env.IMAGE_NAME}:${env.BUILD_NUMBER} ${env.IMAGE_NAME}:latest"
      }
    }

    stage('Test') {
      steps {
        // Simple import test; you can replace with pytest if you have tests
        sh 'docker run --rm '"${env.IMAGE_NAME}"':latest python -c "import flask; print(\'OK\')"'
      }
    }

    stage('Deploy (run container)') {
      steps {
        sh """
          set -euxo pipefail
          docker rm -f ${CONTAINER_NAME} || true
          docker run -d --restart unless-stopped \\
            --name ${CONTAINER_NAME} \\
            -p ${PORT}:${PORT} \\
            ${IMAGE_NAME}:latest
          docker ps --filter "name=${CONTAINER_NAME}"
        """
      }
    }
  }

  post {
    always {
      sh 'docker image ls | head -n 10'
    }
  }
}
